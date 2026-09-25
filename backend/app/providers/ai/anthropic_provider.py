"""Anthropic (Claude) AI provider — chat completions via the Messages API.

Anthropic's Messages API has no native `response_format: json_object` mode
(unlike OpenAI/Groq), so JSON-only output is forced with the standard
assistant-message "prefill" technique: the request's final message is a
pre-filled assistant turn containing just `{`, which stops Claude from
prefacing the reply with prose — it continues directly into the object.
The API returns only the continuation (not the prefill itself), so the
leading `{` is prepended back onto `text` before returning, giving callers
(PersonalizationService, LeadQualificationService, ProspectPromptService)
the same plain `json.loads()`-able output Groq's `json_object` mode gave.

Requires ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json

import httpx

from app.providers.ai.base import AIGenerationRequest, AIGenerationResult, AIProvider
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.http import request_json

_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    name = "anthropic"
    category = ProviderCategory.AI

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("anthropic: ANTHROPIC_API_KEY is not configured")
        self._api_key = api_key
        self._model = model
        # A full max_tokens=4096 completion can legitimately take longer
        # than a typical 30s API timeout — observed one real call time out
        # 3x in a row (~90s total across retries) purely from running long,
        # not from being unreachable. Safe to allow more time now that
        # qualification runs as a background task rather than blocking the
        # search response (see search_service.qualify_contacts_in_background).
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(90.0))

    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        facts = json.dumps(request.source_fields, indent=2)
        payload = await request_json(
            self._client,
            "POST",
            "/v1/messages",
            provider=self.name,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": _API_VERSION,
            },
            json={
                "model": self._model,
                "max_tokens": request.max_tokens,
                "system": request.instructions,
                "messages": [
                    {"role": "user", "content": f"Known facts (JSON):\n{facts}"},
                    {"role": "assistant", "content": "{"},
                ],
            },
        )
        content_blocks = payload.get("content") or []
        if not content_blocks:
            raise ProviderUnavailableError("anthropic: response contained no content")
        continuation = content_blocks[0].get("text")
        if continuation is None:
            raise ProviderUnavailableError("anthropic: response block had no text")

        return AIGenerationResult(
            text="{" + continuation,
            model=payload.get("model", self._model),
            prompt_version=request.prompt_version,
            source_fields_used=list(request.source_fields.keys()),
        )
