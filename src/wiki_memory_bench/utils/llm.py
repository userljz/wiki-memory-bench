"""Shared LiteLLM runtime with retry, cache, and artifact logging."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from litellm import completion, completion_cost

from wiki_memory_bench.schemas import TokenUsage
from wiki_memory_bench.utils.paths import ensure_runtime_dirs, llm_cache_dir


class LiteLLMRuntime:
    """Thin JSON-oriented LiteLLM wrapper for answerers and judges."""

    def __init__(
        self,
        *,
        task_name: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        cache_dir: Path | None = None,
        artifact_dir: Path | None = None,
        max_retries: int = 3,
        sleep_seconds: float = 0.5,
    ) -> None:
        self.task_name = task_name
        self.model = model or os.getenv("LLM_MODEL")
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY")
        self.base_url = base_url if base_url is not None else os.getenv("LLM_BASE_URL")
        self.cache_dir = cache_dir or llm_cache_dir()
        self.artifact_dir = artifact_dir
        self.max_retries = max_retries
        self.sleep_seconds = sleep_seconds

    def set_artifact_dir(self, artifact_dir: Path) -> None:
        """Configure the per-run artifact directory for prompt logs."""

        self.artifact_dir = artifact_dir

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], TokenUsage, dict[str, Any]]:
        """Execute a JSON-only LLM completion with caching and retries."""

        if not self.model:
            raise RuntimeError(
                "LLM_MODEL is not configured. Set LLM_MODEL (and LLM_API_KEY when required) before using llm mode."
            )

        ensure_runtime_dirs()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.artifact_dir is not None:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)

        request_payload = {
            "task_name": self.task_name,
            "model": self.model,
            "base_url": self.base_url,
            "prompt": prompt,
        }
        request_hash = hashlib.sha256(json.dumps(request_payload, sort_keys=True).encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{request_hash}.json"

        if cache_path.exists():
            cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            parsed = cached_payload["parsed_response"]
            usage = TokenUsage.model_validate(cached_payload["token_usage"])
            metadata = {
                "request_hash": request_hash,
                "cached": True,
                "model": self.model,
                "artifact_path": self._write_artifact(request_hash, prompt, {**cached_payload, "cached": True}),
            }
            return parsed, usage, metadata

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = completion(
                    model=self.model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                content = response.choices[0].message.content or ""
                parsed = _extract_json_dict(content)
                try:
                    estimated_cost_usd = float(completion_cost(completion_response=response) or 0.0)
                except Exception:  # pragma: no cover - depends on provider-specific pricing support
                    estimated_cost_usd = 0.0
                usage = TokenUsage(
                    input_tokens=int(getattr(response.usage, "prompt_tokens", 0) or 0),
                    output_tokens=int(getattr(response.usage, "completion_tokens", 0) or 0),
                    estimated_cost_usd=estimated_cost_usd,
                )
                record = {
                    "task_name": self.task_name,
                    "model": self.model,
                    "base_url": self.base_url,
                    "prompt": prompt,
                    "raw_response": content,
                    "parsed_response": parsed,
                    "token_usage": usage.model_dump(mode="json"),
                    "attempt": attempt,
                    "cached": False,
                }
                cache_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                metadata = {
                    "request_hash": request_hash,
                    "cached": False,
                    "model": self.model,
                    "artifact_path": self._write_artifact(request_hash, prompt, record),
                }
                return parsed, usage, metadata
            except Exception as error:  # pragma: no cover - retry branch depends on backend failure
                last_error = error
                if attempt >= self.max_retries:
                    break
                time.sleep(self.sleep_seconds * attempt)

        raise RuntimeError(f"LiteLLM call failed after {self.max_retries} attempts") from last_error

    def _write_artifact(self, request_hash: str, prompt: str, record: dict[str, Any]) -> str | None:
        if self.artifact_dir is None:
            return None
        artifact_path = self.artifact_dir / f"{request_hash}.json"
        payload = {
            "task_name": self.task_name,
            "model": self.model,
            "base_url": self.base_url,
            "prompt": prompt,
            **record,
        }
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(artifact_path)


def _extract_json_dict(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return json.loads(stripped)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object")
    return json.loads(stripped[start : end + 1])
