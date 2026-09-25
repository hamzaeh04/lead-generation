"""Classifies a reply's sentiment (positive/neutral/negative) from its
actual text, via whatever `ai`-category provider is enabled (Anthropic by
default — see provider_factory). Returns None whenever there's no text to
classify or no AI provider is configured/available, same never-fabricate
boundary as every other AI-adjacent feature in this codebase: a missing
classification is a normal outcome, not an error, and is never guessed.
"""
from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.email_event import ReplySentiment
from app.providers.ai.base import AIGenerationRequest
from app.providers.base import ProviderCategory, ProviderUnavailableError
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.services import provider_factory
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Real ESP inbound-reply payloads vary by provider (SendGrid's Inbound
# Parse, Postmark's InboundMessage, Mailgun's routes, ...) — since no
# per-ESP adapter is built yet (see webhooks.py), this checks the common
# plain-text key names a normalized payload is likely to use rather than
# assuming one fixed shape.
_TEXT_KEYS = ("text", "stripped_text", "stripped-text", "body", "plain", "content")

_INSTRUCTIONS = (
    'You classify the sentiment of a cold-outreach email reply. Respond with '
    'JSON only: {"sentiment": "positive"|"neutral"|"negative"}. '
    '"positive" = interested, wants to talk, asks for more info, agrees to a call. '
    '"negative" = explicitly not interested, hostile, or asks to stop contacting them. '
    '"neutral" = anything else (auto-reply, unclear, out of office, ambiguous).'
)


def extract_reply_text(raw_payload: dict) -> str | None:
    for key in _TEXT_KEYS:
        value = raw_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def classify_reply_sentiment(
    session: AsyncSession, settings: Settings, reply_text: str
) -> ReplySentiment | None:
    registry_entries = await ProviderConfigRepository(session).list_enabled_for_category(
        ProviderCategory.AI
    )
    for registry_entry in registry_entries:
        provider = provider_factory.build_provider(
            registry_entry.provider, ProviderCategory.AI, settings
        )
        if provider is None:
            continue
        try:
            result = await provider.generate(
                AIGenerationRequest(
                    prompt_version="reply-sentiment-v1",
                    instructions=_INSTRUCTIONS,
                    source_fields={"reply_text": reply_text},
                    max_tokens=50,
                )
            )
            sentiment = json.loads(result.text).get("sentiment")
        except (ProviderUnavailableError, json.JSONDecodeError, AttributeError) as exc:
            logger.warning(
                "reply_sentiment_classification_failed",
                provider=registry_entry.provider,
                error=str(exc),
            )
            continue

        try:
            return ReplySentiment(sentiment)
        except ValueError:
            logger.warning("reply_sentiment_unrecognized_value", value=sentiment)
            return None
    return None
