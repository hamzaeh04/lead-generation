"""Shared HTTP plumbing for provider integrations.

Every real provider (Apollo, PDL, SerpApi, ...) makes outbound calls through
`request_json`, which retries transient failures, times out sanely, and
converts any failure into `ProviderUnavailableError` so a future waterfall
orchestrator (Phase 6) can fall back to the next provider instead of the
whole operation blowing up. It never retries on 4xx auth/validation errors —
those are the caller's problem, not a transient condition.
"""
from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.providers.base import ProviderUnavailableError
from app.utils.logging import get_logger

logger = get_logger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class _RetryableProviderError(Exception):
    """Internal signal for a transient failure worth retrying."""


def build_http_client(*, base_url: str, timeout_seconds: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(timeout_seconds))


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(_RetryableProviderError),
)
async def _do_request(
    client: httpx.AsyncClient, method: str, url: str, provider: str, **kwargs
) -> httpx.Response:
    try:
        response = await client.request(method, url, **kwargs)
    except httpx.TimeoutException as exc:
        raise _RetryableProviderError(str(exc)) from exc
    except httpx.RequestError as exc:
        raise ProviderUnavailableError(f"{provider}: network error: {exc}") from exc

    if response.status_code in _RETRYABLE_STATUS_CODES:
        raise _RetryableProviderError(f"{provider}: transient HTTP {response.status_code}")

    return response


def _error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of a provider's own error message (e.g.
    Apollo's billing errors, which arrive as a 422 with a real explanation
    in the body) — without this, every non-2xx collapses into a bare
    status code and a genuine cause like "out of credits" looks identical
    to a malformed request, making it impossible to tell apart without
    reproducing the call by hand."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300] if response.text else "no response body"
    if isinstance(body, dict):
        for key in ("message", "error", "detail"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
            error_details = body.get("error_details")
            if isinstance(error_details, dict):
                nested = error_details.get("message")
                if isinstance(nested, str) and nested:
                    return nested
    return str(body)[:300]


async def request_json(
    client: httpx.AsyncClient, method: str, url: str, *, provider: str, **kwargs
) -> dict:
    """Performs an HTTP request and returns the parsed JSON body.

    Raises ProviderUnavailableError for auth failures, exhausted retries,
    network errors, or a non-2xx status that isn't retryable.
    """
    try:
        response = await _do_request(client, method, url, provider, **kwargs)
    except _RetryableProviderError as exc:
        logger.warning("provider_request_exhausted_retries", provider=provider, error=str(exc))
        raise ProviderUnavailableError(f"{provider}: {exc}") from exc

    if response.status_code in (401, 403):
        raise ProviderUnavailableError(f"{provider}: authentication rejected (check API key)")
    if response.status_code >= 400:
        raise ProviderUnavailableError(
            f"{provider}: request failed with HTTP {response.status_code} — {_error_detail(response)}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ProviderUnavailableError(f"{provider}: non-JSON response") from exc
