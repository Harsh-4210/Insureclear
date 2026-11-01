import httpx

from tools import llm_client


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


def test_groq_waits_for_retry_after_then_returns_json(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_API_KEYS", raising=False)
    llm_client._groq_key_index = 0
    llm_client._groq_key_cooldowns.clear()
    responses = [
        FakeResponse(429, headers={"retry-after": "7"}),
        FakeResponse(200, {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"total_tokens": 42},
        }),
    ]
    sent = []
    sleeps = []
    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: sent.append(json) or responses.pop(0))
    monkeypatch.setattr(llm_client.time, "sleep", sleeps.append)

    before = llm_client.get_stats()["total_tokens"]
    assert llm_client.call_llm_json("Return ok") == {"ok": True}

    assert sleeps == [8.0]
    assert sent[0]["response_format"] == {"type": "json_object"}
    assert sent[0]["include_reasoning"] is False
    assert llm_client.get_stats()["total_tokens"] - before == 42


def test_groq_rotates_to_available_pool_key_after_rate_limit(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEYS", "first-key,second-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    llm_client._groq_key_index = 0
    llm_client._groq_key_cooldowns.clear()
    responses = [
        FakeResponse(429, headers={"retry-after": "7"}),
        FakeResponse(200, {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 10},
        }),
    ]
    sent = []
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, json, headers, timeout: sent.append(headers) or responses.pop(0),
    )
    monkeypatch.setattr(llm_client.time, "sleep", lambda _: None)

    assert llm_client.call_llm("Return ok") == "ok"
    assert sent[0]["Authorization"] == "Bearer first-key"
    assert sent[1]["Authorization"] == "Bearer second-key"


def test_groq_reads_numbered_pool_keys(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEYS", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    for name in list(llm_client.os.environ):
        if name.startswith("GROQ_API_KEY_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "second-key")
    monkeypatch.setenv("GROQ_API_KEY_1", "first-key")
    assert llm_client._groq_api_keys() == ["first-key", "second-key"]
