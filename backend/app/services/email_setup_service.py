"""Email Setup CRUD helpers + fixed-column CSV bulk import."""
from __future__ import annotations

import csv
import io
import uuid

from email_validator import EmailNotValidError, validate_email
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.email_setup import EmailSetup
from app.repositories.email_setup_repository import EmailSetupRepository
from app.schemas.email_setup import (
    EmailSetupCreate,
    EmailSetupDefaults,
    EmailSetupImportResult,
    EmailSetupImportRowError,
    EmailSetupRead,
    EmailSetupUpdate,
)

_HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "name": ("name", "label", "account name", "account"),
    "smtp_host": ("smtp_host", "host", "smtp host", "server"),
    "smtp_port": ("smtp_port", "port", "smtp port"),
    "smtp_username": ("smtp_username", "username", "user", "smtp user", "login"),
    "smtp_password": ("smtp_password", "password", "smtp password", "pass"),
    "smtp_from_email": (
        "smtp_from_email",
        "from_email",
        "from email",
        "from",
        "sender",
        "sender email",
    ),
}


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode CSV file (unsupported encoding)")


def _map_headers(headers: list[str]) -> dict[str, str]:
    lowered = {h: h.strip().lower() for h in headers}
    mapping: dict[str, str] = {}
    for canonical, synonyms in _HEADER_SYNONYMS.items():
        for header, lowered_header in lowered.items():
            if lowered_header in synonyms:
                mapping[canonical] = header
                break
    return mapping


def to_read(setup: EmailSetup) -> EmailSetupRead:
    return EmailSetupRead(
        id=setup.id,
        workspace_id=setup.workspace_id,
        name=setup.name,
        smtp_host=setup.smtp_host,
        smtp_port=setup.smtp_port,
        smtp_username=setup.smtp_username,
        smtp_from_email=setup.smtp_from_email,
        is_default=setup.is_default,
        has_password=bool(setup.smtp_password),
        created_at=setup.created_at,
        updated_at=setup.updated_at,
    )


def get_defaults() -> EmailSetupDefaults:
    settings = get_settings()
    return EmailSetupDefaults(
        name="Primary SMTP",
        smtp_host=settings.SMTP_HOST or "smtp.example.com",
        smtp_port=settings.SMTP_PORT or 587,
        smtp_username=settings.SMTP_USERNAME or "you@yourcompany.com",
        smtp_password="your-smtp-password",
        smtp_from_email=settings.SMTP_FROM_EMAIL or "you@yourcompany.com",
    )


class EmailSetupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EmailSetupRepository(session)

    async def create(self, workspace_id: uuid.UUID, payload: EmailSetupCreate) -> EmailSetup:
        if payload.is_default:
            await self.repo.clear_default(workspace_id)
        return self.repo.create(workspace_id=workspace_id, **payload.model_dump())

    async def update(
        self, workspace_id: uuid.UUID, setup_id: uuid.UUID, payload: EmailSetupUpdate
    ) -> EmailSetup | None:
        setup = await self.repo.get_by_id(workspace_id, setup_id)
        if setup is None:
            return None

        data = payload.model_dump(exclude_unset=True)
        if data.get("is_default") is True:
            await self.repo.clear_default(workspace_id, except_id=setup.id)

        for field_name, value in data.items():
            setattr(setup, field_name, value)
        return setup

    async def delete(self, workspace_id: uuid.UUID, setup_id: uuid.UUID) -> bool:
        setup = await self.repo.get_by_id(workspace_id, setup_id)
        if setup is None:
            return False
        await self.repo.delete(setup)
        return True

    async def import_csv(self, workspace_id: uuid.UUID, content: bytes) -> EmailSetupImportResult:
        text = _decode(content)
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        mapping = _map_headers(headers)

        required = ("smtp_host", "smtp_username", "smtp_password", "smtp_from_email")
        missing = [f for f in required if f not in mapping]
        if missing:
            raise ValueError(
                "CSV is missing required columns: "
                + ", ".join(missing)
                + ". Expected headers like smtp_host, smtp_port, smtp_username, "
                "smtp_password, smtp_from_email (and optional name)."
            )

        created = 0
        skipped = 0
        errors: list[EmailSetupImportRowError] = []

        for index, row in enumerate(reader, start=2):
            def cell(field: str) -> str:
                header = mapping.get(field)
                if not header:
                    return ""
                return (row.get(header) or "").strip()

            raw_port = cell("smtp_port") or "587"
            try:
                port = int(raw_port)
            except ValueError:
                errors.append(
                    EmailSetupImportRowError(
                        row_number=index, message=f"Invalid smtp_port: {raw_port!r}"
                    )
                )
                skipped += 1
                continue

            name = cell("name") or f"SMTP {cell('smtp_host') or index}"
            try:
                from_email = validate_email(
                    cell("smtp_from_email"), check_deliverability=False
                ).normalized
            except EmailNotValidError:
                errors.append(
                    EmailSetupImportRowError(
                        row_number=index,
                        message=f"Invalid smtp_from_email: {cell('smtp_from_email')!r}",
                    )
                )
                skipped += 1
                continue

            try:
                payload = EmailSetupCreate(
                    name=name,
                    smtp_host=cell("smtp_host"),
                    smtp_port=port,
                    smtp_username=cell("smtp_username"),
                    smtp_password=cell("smtp_password"),
                    smtp_from_email=from_email,
                    is_default=False,
                )
            except ValidationError as exc:
                errors.append(
                    EmailSetupImportRowError(
                        row_number=index, message="; ".join(e["msg"] for e in exc.errors())
                    )
                )
                skipped += 1
                continue

            await self.create(workspace_id, payload)
            created += 1

        return EmailSetupImportResult(created=created, skipped=skipped, errors=errors)
