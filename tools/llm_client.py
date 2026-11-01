"""
LLM Client
Two providers, picked with LLM_PROVIDER in .env:
  gemini (default) — Gemini Flash via google-generativeai
  groq             — openai/gpt-oss-120b via Groq's OpenAI-compatible API
All agents call this — so if you ever swap models, you change it in one place.
"""

import os
import time
import json
import re
import threading
import httpx
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "medium")

_client_initialised = False
_total_calls = 0
_total_time = 0.0
_total_tokens = 0
_total_retries = 0
_total_429s = 0
_groq_rate_lock = threading.Lock()
_groq_key_index = 0
_groq_key_cooldowns = {}
if PROVIDER == "groq":
    MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    genai = None
else:
    import google.generativeai as genai
    MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


def _init():
    global _client_initialised
    if PROVIDER == "groq":
        if not _groq_api_keys():
            raise EnvironmentError(
                "GROQ_API_KEY or GROQ_API_KEYS not found. Add one to .env."
            )
        return
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
        "provider": PROVIDER,
        "model": MODEL_NAME,
        "total_calls": _total_calls,
        "total_tokens": _total_tokens,
        "total_retries": _total_retries,
        "total_429s": _total_429s,
        "groq_configured_key_count": len(_groq_api_keys()) if PROVIDER == "groq" else 0,
        "total_time_seconds": round(_total_time, 2),
        "avg_time_per_call": round(_total_time / max(_total_calls, 1), 2),
    }


def _groq_api_keys() -> list[str]:
    """Return configured keys from a pool or numbered environment variables."""
    pool = [key.strip() for key in os.getenv("GROQ_API_KEYS", "").split(",") if key.strip()]
    if pool:
        return pool

    numbered = []
    for name, value in os.environ.items():
        match = re.fullmatch(r"GROQ_API_KEY_(\d+)", name)
        if match and value.strip():
            numbered.append((int(match.group(1)), value.strip()))
    if numbered:
        return [value for _, value in sorted(numbered)]

    key = os.getenv("GROQ_API_KEY", "").strip()
    return [key] if key else []


def _select_groq_key() -> tuple[str, float]:
    """Select an available key and return any required cooldown wait."""
    global _groq_key_index
    keys = _groq_api_keys()
    now = time.time()
    with _groq_rate_lock:
        for offset in range(len(keys)):
            index = (_groq_key_index + offset) % len(keys)
            key = keys[index]
            if _groq_key_cooldowns.get(key, 0.0) <= now:
                _groq_key_index = (index + 1) % len(keys)
                return key, 0.0
        wait = min(_groq_key_cooldowns.get(key, now) for key in keys) - now
        return keys[_groq_key_index % len(keys)], max(wait, 0.0)


def _call_groq(
    prompt: str,
    system_prompt: str,
    temperature: float,
    max_output_tokens: int,
    json_mode: bool,
    max_retries: int = 6,
) -> str:
    """
    One Groq chat completion. On 429 it waits for the time Groq asks for
    (retry-after header) instead of a fixed short backoff.
    """
    global _total_calls, _total_time, _total_tokens, _total_retries, _total_429s

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        # gpt-oss reasoning tokens count toward this limit, so leave room for them
        "max_completion_tokens": max_output_tokens + 4096,
        "reasoning_effort": GROQ_REASONING_EFFORT,
        "include_reasoning": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"}

    for attempt in range(1, max_retries + 1):
        groq_key, key_wait = _select_groq_key()
        if key_wait > 0:
            time.sleep(key_wait)

        start = time.time()
        try:
            response = httpx.post(
                GROQ_URL,
                json=body,
                headers={"Authorization": f"Bearer {groq_key}"},
                timeout=180,
            )
        except httpx.HTTPError as e:
            _total_retries += 1
            if attempt == max_retries:
                raise RuntimeError(f"Groq call failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)
            continue

        if response.status_code == 429:
            _total_429s += 1
            _total_retries += 1
            if attempt == max_retries:
                raise RuntimeError(f"Groq call failed after {max_retries} attempts: {response.text[:300]}")
            wait = _groq_retry_wait(response.headers, attempt)
            with _groq_rate_lock:
                _groq_key_cooldowns[groq_key] = time.time() + wait
            print(
                f"[llm] Groq 429. Key cooled down for {wait:.1f}s; "
                f"trying another key (retry {attempt}/{max_retries})..."
            )
            continue
        if response.status_code >= 500:
            _total_retries += 1
            if attempt == max_retries:
                raise RuntimeError(f"Groq call failed after {max_retries} attempts: {response.text[:300]}")
            wait = float(2 ** attempt)
            print(f"[llm] Groq {response.status_code}. Waiting {wait:.0f}s before retry {attempt}/{max_retries}...")
            time.sleep(wait)
            continue
        if response.status_code != 200:
            raise RuntimeError(f"Groq error {response.status_code}: {response.text[:500]}")

        data = response.json()
        _total_calls += 1
        _total_time += time.time() - start
        _total_tokens += data.get("usage", {}).get("total_tokens", 0)
        return (data["choices"][0]["message"].get("content") or "").strip()

    raise RuntimeError("Groq call exhausted all retries.")


def _duration_seconds(value: str | None) -> float | None:
    """Parse Groq reset values such as '7.66s' or '2m59.56s'."""
    if not value:
        return None
    match = re.fullmatch(
        r"\s*(?:(?P<hours>\d+(?:\.\d+)?)h)?"
        r"\s*(?:(?P<minutes>\d+(?:\.\d+)?)m)?"
        r"\s*(?:(?P<seconds>\d+(?:\.\d+)?)s)?\s*",
        value,
        re.IGNORECASE,
    )
    if match and any(match.group(name) for name in ("hours", "minutes", "seconds")):
        return (
            float(match.group("hours") or 0) * 3600
            + float(match.group("minutes") or 0) * 60
            + float(match.group("seconds") or 0)
        )
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _groq_retry_wait(headers, attempt: int) -> float:
    """Honor Groq's retry-after/reset headers, with exponential fallback."""
    retry_after = _duration_seconds(headers.get("retry-after"))
    if retry_after is not None:
        return max(retry_after + 1.0, 0.0)

    reset_values = [
        _duration_seconds(headers.get("x-ratelimit-reset-tokens")),
        _duration_seconds(headers.get("x-ratelimit-reset-requests")),
    ]
    reset_waits = [value for value in reset_values if value is not None]
    return max(reset_waits, default=float(2 ** attempt))


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
    global _total_calls, _total_time, _total_retries, _total_429s
    _init()

    if PROVIDER == "groq":
        return _call_groq(prompt, system_prompt, temperature, max_output_tokens, json_mode=False)

    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
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
            _total_retries += 1
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str:
                _total_429s += 1
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
    except (ValueError, KeyError, json.JSONDecodeError):
        pass
    except RuntimeError as error:
        if "json_validate_failed" not in str(error):
            raise

    # Fallback: standard call + parse
    raw = call_llm(
        prompt + json_instruction,
        system_prompt=system_prompt,
        temperature=0.1,
        max_retries=max_retries,
    )
    return _parse_json_response(raw)


def _call_native_json(prompt: str, system_prompt: str, max_retries: int) -> dict:
    """Use the provider's native JSON response mode."""
    global _total_calls, _total_time, _total_retries, _total_429s

    if PROVIDER == "groq":
        raw = _call_groq(prompt, system_prompt, 0.1, 4096, json_mode=True)
        return _parse_json_response(raw)

    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
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
            _total_retries += 1
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                _total_429s += 1
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
