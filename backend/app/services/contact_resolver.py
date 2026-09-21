"""PersonEntityResolver: dedup + provenance for incoming contact records.

Matches only on strong signals (exact email, exact LinkedIn URL). A
name+company match is deliberately NOT used on its own — common names at
the same company could belong to different people — so two people who
only share a name and employer are kept as separate contacts.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.models.contact import Contact
from app.providers.base import NormalizedContact
from app.repositories.contact_repository import ContactRepository
from app.services.normalization import normalize_email, normalize_phone

_CONTACT_FIELDS = (
    "first_name", "last_name", "full_name", "job_title", "department",
    "seniority", "email", "phone", "linkedin_url",
    "city", "state", "country", "industry", "sub_industry",
    "company_headcount", "company_revenue",
)


class MatchConfidence(StrEnum):
    HIGH = "high"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ContactResolution:
    contact: Contact
    created: bool
    matched_fields: list[str]
    confidence: MatchConfidence


class PersonEntityResolver:
    def __init__(self, repo: ContactRepository) -> None:
        self.repo = repo

    async def resolve(
        self,
        *,
        workspace_id: uuid.UUID,
        candidate: NormalizedContact,
        company_id: uuid.UUID | None,
    ) -> ContactResolution:
        email = normalize_email(candidate.email)
        phone = normalize_phone(candidate.phone)

        existing, matched_fields = await self._find_match(
            workspace_id=workspace_id, email=email, linkedin_url=candidate.linkedin_url
        )

        provider = candidate.metadata.provider
        retrieved_at = candidate.metadata.retrieved_at.isoformat()

        if existing is not None:
            self._fill_missing_fields(existing, candidate, email, phone, provider, retrieved_at)
            self.repo.add_source(
                contact=existing,
                provider=provider,
                external_id=candidate.metadata.external_id,
                source_url=candidate.metadata.source_url,
                source_type=candidate.metadata.source_type,
                raw_reference=candidate.metadata.raw_reference,
            )
            return ContactResolution(existing, False, matched_fields, MatchConfidence.HIGH)

        full_name = candidate.full_name or _join_name(candidate.first_name, candidate.last_name)
        contact = await self.repo.create(
            workspace_id=workspace_id,
            company_id=company_id,
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            full_name=full_name,
            job_title=candidate.job_title,
            department=candidate.department,
            seniority=candidate.seniority,
            email=email,
            phone=phone,
            linkedin_url=candidate.linkedin_url,
            city=candidate.city,
            state=candidate.state,
            country=candidate.country,
            industry=candidate.industry,
            sub_industry=candidate.sub_industry,
            company_headcount=candidate.company_headcount,
            company_revenue=candidate.company_revenue,
            field_provenance=self._provenance_for_set_fields(candidate, provider, retrieved_at),
        )
        self.repo.add_source(
            contact=contact,
            provider=provider,
            external_id=candidate.metadata.external_id,
            source_url=candidate.metadata.source_url,
            source_type=candidate.metadata.source_type,
            raw_reference=candidate.metadata.raw_reference,
        )
        return ContactResolution(contact, True, [], MatchConfidence.NONE)

    async def _find_match(
        self, *, workspace_id: uuid.UUID, email: str | None, linkedin_url: str | None
    ) -> tuple[Contact | None, list[str]]:
        if email:
            match = await self.repo.find_by_email(workspace_id, email)
            if match is not None:
                return match, ["email"]

        if linkedin_url:
            match = await self.repo.find_by_linkedin_url(workspace_id, linkedin_url)
            if match is not None:
                return match, ["linkedin_url"]

        return None, []

    def _fill_missing_fields(
        self,
        contact: Contact,
        candidate: NormalizedContact,
        email: str | None,
        phone: str | None,
        provider: str,
        retrieved_at: str,
    ) -> None:
        provenance = dict(contact.field_provenance)
        incoming_values = {
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "full_name": candidate.full_name,
            "job_title": candidate.job_title,
            "department": candidate.department,
            "seniority": candidate.seniority,
            "email": email,
            "phone": phone,
            "linkedin_url": candidate.linkedin_url,
            "city": candidate.city,
            "state": candidate.state,
            "country": candidate.country,
            "industry": candidate.industry,
            "sub_industry": candidate.sub_industry,
            "company_headcount": candidate.company_headcount,
            "company_revenue": candidate.company_revenue,
        }
        for field_name, incoming in incoming_values.items():
            current = getattr(contact, field_name)
            if current is None and incoming is not None:
                setattr(contact, field_name, incoming)
                provenance[field_name] = {"provider": provider, "retrieved_at": retrieved_at}
        contact.field_provenance = provenance

    def _provenance_for_set_fields(
        self, candidate: NormalizedContact, provider: str, retrieved_at: str
    ) -> dict[str, Any]:
        provenance: dict[str, Any] = {}
        for field_name in _CONTACT_FIELDS:
            if getattr(candidate, field_name, None) is not None:
                provenance[field_name] = {"provider": provider, "retrieved_at": retrieved_at}
        return provenance


def _join_name(first_name: str | None, last_name: str | None) -> str | None:
    parts = [p for p in (first_name, last_name) if p]
    return " ".join(parts) if parts else None
