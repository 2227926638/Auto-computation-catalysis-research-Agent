from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMError(RuntimeError):
    pass


class LLMDisabledError(LLMError):
    pass


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    model: str
    content: str
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


@dataclass
class DeepSeekSettings:
    enabled: bool = False
    api_key: str = ""
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    timeout_seconds: float = 120.0
    max_retries: int = 1
    retry_sleep_seconds: float = 2.0
    temperature: float = 0.2
    max_tokens: int = 4096
    thinking_type: str = "disabled"
    reasoning_effort: str = "high"
    user_agent: str = "catalysis-question-agent/0.1"

    @property
    def resolved_api_key(self) -> str:
        return self.api_key or os.environ.get(self.api_key_env, "")


class DeepSeekChatClient:
    """Small OpenAI-compatible DeepSeek chat client using stdlib urllib."""

    def __init__(self, settings: DeepSeekSettings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def chat_text(self, messages: list[dict[str, str]], *, max_tokens: int | None = None) -> LLMResponse:
        return self._chat(messages, json_mode=False, max_tokens=max_tokens)

    def chat_json(self, messages: list[dict[str, str]], *, max_tokens: int | None = None) -> dict[str, Any]:
        response = self._chat(messages, json_mode=True, max_tokens=max_tokens)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"DeepSeek returned non-JSON content: {exc}") from exc

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if not self.settings.enabled:
            raise LLMDisabledError("LLM is disabled in config.")
        api_key = self.settings.resolved_api_key
        if not api_key:
            raise LLMError(
                "DeepSeek API key is empty. Fill llm.api_key in the YAML config "
                f"or set the {self.settings.api_key_env} environment variable."
            )

        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        body: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
            "temperature": self.settings.temperature,
            "max_tokens": max_tokens or self.settings.max_tokens,
            "thinking": {"type": self.settings.thinking_type},
            "reasoning_effort": self.settings.reasoning_effort,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                raw = self._post_json(url, body, api_key)
                choice = (raw.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                content = message.get("content") or ""
                if not content:
                    raise LLMError("DeepSeek returned an empty message content.")
                return LLMResponse(
                    provider="deepseek",
                    model=self.settings.model,
                    content=content,
                    usage=raw.get("usage") or {},
                    raw=raw,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                time.sleep(self.settings.retry_sleep_seconds)
        raise LLMError(f"DeepSeek chat request failed: {last_error}") from last_error

    def _post_json(self, url: str, body: dict[str, Any], api_key: str) -> dict[str, Any]:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": self.settings.user_agent,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"HTTP {exc.code}: {detail}") from exc


def llm_client_from_config(config: dict[str, Any]) -> DeepSeekChatClient:
    llm = config.get("llm", {}) or {}
    thinking = llm.get("thinking", {}) or {}
    settings = DeepSeekSettings(
        enabled=bool(llm.get("enabled", False)),
        api_key=str(llm.get("api_key", "") or ""),
        api_key_env=str(llm.get("api_key_env", "DEEPSEEK_API_KEY")),
        base_url=str(llm.get("base_url", "https://api.deepseek.com")),
        model=str(llm.get("model", "deepseek-v4-pro")),
        timeout_seconds=float(llm.get("timeout_seconds", 120)),
        max_retries=int(llm.get("max_retries", 1)),
        retry_sleep_seconds=float(llm.get("retry_sleep_seconds", 2)),
        temperature=float(llm.get("temperature", 0.2)),
        max_tokens=int(llm.get("max_tokens", 4096)),
        thinking_type=str(thinking.get("type", "disabled")),
        reasoning_effort=str(thinking.get("reasoning_effort", "high")),
        user_agent=str(llm.get("user_agent", "catalysis-question-agent/0.1")),
    )
    return DeepSeekChatClient(settings)
