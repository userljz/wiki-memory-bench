from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "tencent/hy3-preview:free"


def _openrouter_model() -> str:
    model = os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL") or DEFAULT_OPENROUTER_MODEL
    if model.startswith("openrouter/"):
        return model.removeprefix("openrouter/")
    if model == "openrouter":
        return DEFAULT_OPENROUTER_MODEL
    return model


def _message_content_is_valid(content: object) -> bool:
    if content is None:
        return True
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return bool(content)
    return False


@pytest.mark.skipif(
    os.getenv("WMB_RUN_OPENROUTER_TEST") != "1",
    reason="Set WMB_RUN_OPENROUTER_TEST=1 to run a real OpenRouter completion test.",
)
def test_openrouter_chat_completion_returns_response() -> None:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY or OPENROUTER_API_KEY is not configured.")

    request_body = {
        "model": _openrouter_model(),
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "temperature": 0,
        "max_tokens": 16,
    }
    request = urllib.request.Request(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:500]
        pytest.fail(f"OpenRouter completion failed with HTTP {error.code}: {body}")
    except OSError as error:
        pytest.fail(f"OpenRouter completion request failed: {error}")

    if "error" in payload:
        pytest.fail(f"OpenRouter completion returned an error payload: {payload['error']}")

    choices = payload.get("choices", [])
    assert choices, payload

    choice = choices[0]
    if "error" in choice:
        pytest.fail(f"OpenRouter completion returned a choice error: {choice['error']}")

    message = choice.get("message")
    assert isinstance(message, dict), payload
    assert message.get("role") == "assistant", payload
    assert _message_content_is_valid(message.get("content")), payload
