"""Self-hosted open-tracking pixel for campaign emails sent via this app's
own SMTP path. Plain SMTP has no delivery/open telemetry of its own — no
ESP webhook is ever going to tell us this happened — so
CampaignSendingService embeds an <img> tag pointing here into every sent
email (see _process_recipient), and a hit on this endpoint is the "read
receipt" signal. Same caveat as every tracking-pixel implementation,
including paid ESPs': Apple Mail Privacy Protection and Gmail's image
proxy can pre-fetch images regardless of whether the recipient actually
opened the message, so this is a signal, not a guarantee.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.campaign_recipient import CampaignRecipient, RecipientStatus
from app.models.contact import Contact, LeadStatus
from app.models.email_event import EmailEventType
from app.repositories.email_event_repository import EmailEventRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/track", tags=["tracking"])

# 1x1 transparent GIF, returned unconditionally (even for an unknown/
# malformed token) so a dead pixel never renders as a broken-image icon
# in the recipient's inbox.
_PIXEL = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b"
)

# Only ever upgrades recipient/contact status toward "opened" — never
# downgrades something further along (e.g. already CLICKED/REPLIED).
# Deliberately a "not already past opened" set rather than "is sent",
# since a single-step campaign's recipient goes straight to COMPLETED
# once sent (see CampaignSendingService._process_recipient) — SENT is
# never the terminal recipient status for a one-step campaign.
_RECIPIENT_ALREADY_PAST_OPEN = {
    RecipientStatus.OPENED,
    RecipientStatus.CLICKED,
    RecipientStatus.REPLIED,
}
_CONTACT_UPGRADE_FROM = {
    LeadStatus.NEW,
    LeadStatus.VERIFIED,
    LeadStatus.READY_FOR_OUTREACH,
    LeadStatus.CONTACTED,
}


@router.get("/open/{recipient_id}.png")
async def track_open(
    recipient_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> Response:
    recipient = await session.get(CampaignRecipient, recipient_id)
    if recipient is not None:
        EmailEventRepository(session).create(
            workspace_id=recipient.workspace_id,
            campaign_recipient_id=recipient.id,
            event_type=EmailEventType.OPENED,
            raw_payload={"source": "tracking_pixel"},
            occurred_at=datetime.now(timezone.utc),
        )
        if recipient.status not in _RECIPIENT_ALREADY_PAST_OPEN:
            recipient.status = RecipientStatus.OPENED

        contact = await session.get(Contact, recipient.contact_id)
        if contact is not None and contact.status in _CONTACT_UPGRADE_FROM:
            contact.status = LeadStatus.OPENED

        await session.commit()
        logger.info("email_open_tracked", campaign_recipient_id=str(recipient.id))

    return Response(content=_PIXEL, media_type="image/gif")
