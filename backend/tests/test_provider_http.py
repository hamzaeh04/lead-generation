"""request_json's error-detail extraction — the one thing that made the
Apollo "out of credits" failure invisible until reproduced by hand: every
non-2xx used to collapse into a bare status code, discarding the
provider's own explanation."""
from __future__ import annotations

import httpx
import pytest

from app.providers.base import ProviderUnavailableError
from app.providers.http import request_json

pytestmark = pytest.mark.asyncio


def _client_for(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="https://example.test")


async def test_surfaces_nested_error_details_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "error": "You have insufficient credits!",
                "error_details": {
                    "code": "BILLING.LIMIT.CREDITS_EXHAUSTED",
                    "message": "Your team has used all of its credits for this billing cycle.",
                },
            },
        )

    client = _client_for(handler)
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await request_json(client, "POST", "/people/match", provider="apollo", json={"id": "x"})

    assert "Your team has used all of its credits for this billing cycle." in str(exc_info.value)


async def test_falls_back_to_top_level_error_field_when_no_nested_details():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid id format"})

    client = _client_for(handler)
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await request_json(client, "POST", "/people/match", provider="apollo", json={"id": "x"})

    assert "invalid id format" in str(exc_info.value)


async def test_non_json_error_body_falls_back_to_raw_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="plain text failure")

    client = _client_for(handler)
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await request_json(client, "POST", "/people/match", provider="apollo", json={"id": "x"})

    assert "plain text failure" in str(exc_info.value)
