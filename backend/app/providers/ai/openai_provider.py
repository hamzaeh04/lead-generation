"""OpenAI-compatible AI provider (chat completions, JSON output).

Built against OpenAI's Chat Completions API — `Authorization: Bearer`,
`/v1/chat/completions`, `response_format: {"type": "json_object"}` for
structured output. This is one of the most stable, widely-documented APIs
in the industry; unlike Apollo/PDL (Phase 3), I'm confident in this shape
without a live-account caveat. Works with any OpenAI-compatible endpoint
(Azure OpenAI, local vLLM/Ollama gateways, etc.) via a custom base_url.

Grounding is NOT enforced here — this provider just calls the model with
whatever instructions/facts it's given. The no-fabrication guarantee lives
in the caller (PersonalizationService), which controls what facts ever
reach `source_fields` in the first place. An LLM can still hallucinate
despite correct instructions; nothing in this codebase can make that
impossible, only reduce its likelihood via strict prompting.

Requires OPENAI_API_KEY.
"""
from __future__ import annotations

import json

import httpx

from app.providers.ai.base import AIGenerationRequest, AIGenerationResult, AIProvider
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.providers.http import request_json

_BASE_URL = "https://api.openai.com"


class OpenAIProvider(AIProvider):
    name = "openai"
    category = ProviderCategory.AI

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        if not api_key:
            raise ProviderUnavailableError("openai: OPENAI_API_KEY is not configured")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=httpx.Timeout(30.0))

    async def generate(self, request: AIGenerationRequest) -> AIGenerationResult:
        facts = json.dumps(request.source_fields, indent=2)
        user_content = (
            f"Score this lead.\n\n{facts}"
            if "lead_record" in request.source_fields
            else f"Known facts (JSON):\n{facts}"
        )
        payload = await request_json(
            self._client,
            "POST",
            "/v1/chat/completions",
            provider=self.name,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": request.instructions},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": request.max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderUnavailableError("openai: response contained no choices")
        content = choices[0].get("message", {}).get("content")
        if not content:
            raise ProviderUnavailableError("openai: response message had no content")

        return AIGenerationResult(
            text=content,
            model=payload.get("model", self._model),
            prompt_version=request.prompt_version,
            source_fields_used=list(request.source_fields.keys()),
        )
