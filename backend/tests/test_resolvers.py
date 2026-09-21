import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.company import CompanySource
from app.models.contact import ContactSource
from app.providers.base import NormalizedCompany, NormalizedContact, ProviderMetadata
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.services.company_resolver import CompanyEntityResolver, MatchConfidence as CompanyConfidence
from app.services.contact_resolver import MatchConfidence as ContactConfidence, PersonEntityResolver

pytestmark = pytest.mark.asyncio


async def _count_company_sources(db_session, company_id) -> int:
    result = await db_session.execute(
        select(CompanySource).where(CompanySource.company_id == company_id)
    )
    return len(result.scalars().all())


async def _count_contact_sources(db_session, contact_id) -> int:
    result = await db_session.execute(
        select(ContactSource).where(ContactSource.contact_id == contact_id)
    )
    return len(result.scalars().all())


def _company_candidate(**overrides) -> NormalizedCompany:
    defaults = dict(
        metadata=ProviderMetadata(
            provider="mock_company_discovery",
            external_id="ext-1",
            source_type="mock_fixture",
            retrieved_at=datetime.now(timezone.utc),
        ),
        name="Acme Dental Group",
        domain="acmedental.example",
        website="https://acmedental.example",
        city="Miami",
        state="FL",
    )
    defaults.update(overrides)
    return NormalizedCompany(**defaults)


async def test_company_resolver_creates_new_company(db_session):
    resolver = CompanyEntityResolver(CompanyRepository(db_session))
    workspace_id = uuid.uuid4()

    resolution = await resolver.resolve(workspace_id=workspace_id, candidate=_company_candidate())

    assert resolution.created is True
    assert resolution.confidence == CompanyConfidence.NONE
    assert resolution.company.domain == "acmedental.example"
    assert resolution.company.normalized_name == "acme dental group"
    assert resolution.company.field_provenance["name"]["provider"] == "mock_company_discovery"
    assert await _count_company_sources(db_session, resolution.company.id) == 1


async def test_company_resolver_matches_on_domain_and_fills_missing_fields(db_session):
    resolver = CompanyEntityResolver(CompanyRepository(db_session))
    workspace_id = uuid.uuid4()

    first = await resolver.resolve(workspace_id=workspace_id, candidate=_company_candidate())

    second_candidate = _company_candidate(
        metadata=ProviderMetadata(
            provider="second_provider",
            external_id="ext-2",
            source_type="api",
            retrieved_at=datetime.now(timezone.utc),
        ),
        employee_count=12,
        phone="+15550100001",
    )
    second = await resolver.resolve(workspace_id=workspace_id, candidate=second_candidate)

    assert second.created is False
    assert second.matched_fields == ["domain"]
    assert second.company.id == first.company.id
    # Field that was missing on the first pass gets filled by the second source.
    assert second.company.employee_count == 12
    assert second.company.field_provenance["employee_count"]["provider"] == "second_provider"
    # Field already set by the first source is never overwritten.
    assert second.company.field_provenance["name"]["provider"] == "mock_company_discovery"
    assert await _count_company_sources(db_session, second.company.id) == 2


async def test_company_resolver_does_not_match_unrelated_company(db_session):
    """Different domain AND different name/location -> no match signal at
    all, so a second, unrelated company is created rather than merged."""
    resolver = CompanyEntityResolver(CompanyRepository(db_session))
    workspace_id = uuid.uuid4()

    await resolver.resolve(workspace_id=workspace_id, candidate=_company_candidate())
    other = await resolver.resolve(
        workspace_id=workspace_id,
        candidate=_company_candidate(
            name="Sunshine Roofing Co",
            domain="sunshineroofing.example",
            website="https://sunshineroofing.example",
            city="Dallas",
            state="TX",
        ),
    )

    assert other.created is True


async def test_company_resolver_matches_on_name_and_location_when_domain_differs(db_session):
    """Same normalized name + city/state but a different domain is still a
    medium-confidence match — e.g. a provider returning a slightly
    different tracking subdomain for a business already on file."""
    resolver = CompanyEntityResolver(CompanyRepository(db_session))
    workspace_id = uuid.uuid4()

    first = await resolver.resolve(workspace_id=workspace_id, candidate=_company_candidate())
    other = await resolver.resolve(
        workspace_id=workspace_id,
        candidate=_company_candidate(domain="different.example", website="https://different.example"),
    )

    assert other.created is False
    assert other.confidence == CompanyConfidence.MEDIUM
    assert other.company.id == first.company.id


def _contact_candidate(**overrides) -> NormalizedContact:
    defaults = dict(
        metadata=ProviderMetadata(
            provider="mock_person_discovery",
            external_id="person-1",
            source_type="mock_fixture",
            retrieved_at=datetime.now(timezone.utc),
        ),
        first_name="Jordan",
        last_name="Alvarez",
        email="jordan@acmedental.example",
    )
    defaults.update(overrides)
    return NormalizedContact(**defaults)


async def test_contact_resolver_creates_new_contact(db_session):
    resolver = PersonEntityResolver(ContactRepository(db_session))
    workspace_id = uuid.uuid4()

    resolution = await resolver.resolve(
        workspace_id=workspace_id, candidate=_contact_candidate(), company_id=None
    )

    assert resolution.created is True
    assert resolution.contact.email == "jordan@acmedental.example"
    assert resolution.contact.full_name == "Jordan Alvarez"


async def test_contact_resolver_matches_on_email(db_session):
    resolver = PersonEntityResolver(ContactRepository(db_session))
    workspace_id = uuid.uuid4()

    first = await resolver.resolve(
        workspace_id=workspace_id, candidate=_contact_candidate(), company_id=None
    )
    second_candidate = _contact_candidate(
        metadata=ProviderMetadata(
            provider="apollo",
            external_id=None,
            source_type="api",
            retrieved_at=datetime.now(timezone.utc),
        ),
        job_title="Owner",
    )
    second = await resolver.resolve(
        workspace_id=workspace_id, candidate=second_candidate, company_id=None
    )

    assert second.created is False
    assert second.matched_fields == ["email"]
    assert second.contact.id == first.contact.id
    assert second.contact.job_title == "Owner"
    assert second.contact.field_provenance["job_title"]["provider"] == "apollo"
    assert second.confidence == ContactConfidence.HIGH


async def test_contact_resolver_keeps_different_emails_separate(db_session):
    resolver = PersonEntityResolver(ContactRepository(db_session))
    workspace_id = uuid.uuid4()

    await resolver.resolve(workspace_id=workspace_id, candidate=_contact_candidate(), company_id=None)
    other = await resolver.resolve(
        workspace_id=workspace_id,
        candidate=_contact_candidate(email="someone.else@acmedental.example"),
        company_id=None,
    )

    assert other.created is True
