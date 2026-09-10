"""
LLM Client
Gemini 2.0 Flash as primary model.
All agents call this — so if you ever swap models, you change it in one place.
"""

import os
import time
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_client_initialised = False
_total_calls = 0
_total_time = 0.0


def _init():
    global _client_initialised
    if not _client_initialised:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY not found. Create a .env file with:\nGEMINI_API_KEY=your_key_here"
            )
        genai.configure(api_key=api_key)
        _client_initialised = True


def get_stats() -> dict:
    """Return LLM usage stats for this session."""
    return {
        "total_calls": _total_calls,
        "total_time_seconds": round(_total_time, 2),
        "avg_time_per_call": round(_total_time / max(_total_calls, 1), 2),
    }


def call_llm(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.2,
    max_retries: int = 3,
    max_output_tokens: int = 4096,
) -> str:
    """
    Call Gemini with a prompt. Returns the response text.
    Retries on rate limit / transient errors with exponential backoff.
    temperature=0.2 keeps outputs factual and consistent (not creative).
    """
    global _total_calls, _total_time
    _init()

    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )

    for attempt in range(1, max_retries + 1):
        try:
            start = time.time()
            response = model.generate_content(full_prompt)
            elapsed = time.time() - start
            _total_calls += 1
            _total_time += elapsed
            return response.text.strip()
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str:
                wait = 2 ** attempt
                print(f"[llm] Rate limit hit. Waiting {wait}s before retry {attempt}/{max_retries}...")
                time.sleep(wait)
            elif attempt < max_retries:
                print(f"[llm] Error: {e}. Retrying ({attempt}/{max_retries})...")
                time.sleep(2)
            else:
                raise RuntimeError(f"LLM call failed after {max_retries} attempts: {e}")

    raise RuntimeError("LLM call exhausted all retries.")


def call_llm_json(prompt: str, system_prompt: str = "", max_retries: int = 3) -> dict:
    """
    Call LLM and parse JSON response.
    Uses Gemini's native JSON mode for reliable structured output.
    Falls back to regex extraction if native mode fails.
    """
    _init()

    json_instruction = "\n\nIMPORTANT: Respond with ONLY valid JSON. No explanation, no markdown code blocks, no preamble."

    # Try native JSON mode first
    try:
        return _call_native_json(prompt + json_instruction, system_prompt, max_retries)
    except Exception:
        pass

    # Fallback: standard call + parse
    raw = call_llm(
        prompt + json_instruction,
        system_prompt=system_prompt,
        temperature=0.1,
        max_retries=max_retries,
    )
    return _parse_json_response(raw)


def _call_native_json(prompt: str, system_prompt: str, max_retries: int) -> dict:
    """Use Gemini's native JSON response mode."""
    global _total_calls, _total_time

    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    for attempt in range(1, max_retries + 1):
        try:
            start = time.time()
            response = model.generate_content(full_prompt)
            elapsed = time.time() - start
            _total_calls += 1
            _total_time += elapsed
            return json.loads(response.text.strip())
        except json.JSONDecodeError:
            raw = response.text.strip()
            return _parse_json_response(raw)
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise

    raise RuntimeError("Native JSON call exhausted all retries.")


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences and extra text."""
    # Strip markdown fences
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"LLM returned invalid JSON.\n\nRaw output:\n{raw[:500]}")
