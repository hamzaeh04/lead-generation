"""Email Setup CRUD helpers + fixed-column CSV bulk import (global)."""
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
    "smtp_email": (
        "smtp_email",
        "email",
        "smtp_username",
        "username",
        "smtp_from_email",
        "from_email",
        "from email",
    ),
    "smtp_password": ("smtp_password", "password", "smtp password", "pass"),
    "smtp_use_tls": ("smtp_use_tls", "use_tls", "tls", "starttls"),
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


def _parse_bool(value: str, *, default: bool = True) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def to_read(setup: EmailSetup) -> EmailSetupRead:
    return EmailSetupRead(
        id=setup.id,
        name=setup.name,
        smtp_host=setup.smtp_host,
        smtp_port=setup.smtp_port,
        smtp_email=setup.smtp_email,
        smtp_use_tls=setup.smtp_use_tls,
        is_default=setup.is_default,
        has_password=bool(setup.smtp_password),
        created_at=setup.created_at,
        updated_at=setup.updated_at,
    )


def get_defaults() -> EmailSetupDefaults:
    settings = get_settings()
    email = settings.SMTP_USERNAME or settings.SMTP_FROM_EMAIL or "you@yourcompany.com"
    return EmailSetupDefaults(
        name="Primary SMTP",
        smtp_host=settings.SMTP_HOST or "smtp.gmail.com",
        smtp_port=settings.SMTP_PORT or 587,
        smtp_email=email,
        smtp_password="your-smtp-password",
        smtp_use_tls=settings.SMTP_USE_TLS,
    )


class EmailSetupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EmailSetupRepository(session)

    async def _ensure_unique_email(
        self,
        smtp_email: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        existing = await self.repo.get_by_email(smtp_email, exclude_id=exclude_id)
        if existing is not None:
            raise ValueError(
                f"An email setup with address '{smtp_email.strip().lower()}' already exists"
            )

    async def create(self, payload: EmailSetupCreate) -> EmailSetup:
        await self._ensure_unique_email(str(payload.smtp_email))
        if payload.is_default:
            await self.repo.clear_default()
        data = payload.model_dump()
        data["smtp_email"] = str(payload.smtp_email).strip().lower()
        return self.repo.create(**data)

    async def update(self, setup_id: uuid.UUID, payload: EmailSetupUpdate) -> EmailSetup | None:
        setup = await self.repo.get_by_id(setup_id)
        if setup is None:
            return None

        data = payload.model_dump(exclude_unset=True)
        if "smtp_email" in data and data["smtp_email"] is not None:
            email = str(data["smtp_email"]).strip().lower()
            await self._ensure_unique_email(email, exclude_id=setup.id)
            data["smtp_email"] = email

        if data.get("is_default") is True:
            await self.repo.clear_default(except_id=setup.id)

        for field_name, value in data.items():
            setattr(setup, field_name, value)
        return setup

    async def delete(self, setup_id: uuid.UUID) -> bool:
        setup = await self.repo.get_by_id(setup_id)
        if setup is None:
            return False
        await self.repo.delete(setup)
        return True

    async def import_csv(self, content: bytes) -> EmailSetupImportResult:
        text = _decode(content)
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        mapping = _map_headers(headers)

        required = ("smtp_host", "smtp_email", "smtp_password")
        missing = [f for f in required if f not in mapping]
        if missing:
            raise ValueError(
                "CSV is missing required columns: "
                + ", ".join(missing)
                + ". Expected headers like name, smtp_host, smtp_port, smtp_email, "
                "smtp_password, smtp_use_tls."
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
                email = validate_email(cell("smtp_email"), check_deliverability=False).normalized
            except EmailNotValidError:
                errors.append(
                    EmailSetupImportRowError(
                        row_number=index,
                        message=f"Invalid smtp_email: {cell('smtp_email')!r}",
                    )
                )
                skipped += 1
                continue

            try:
                payload = EmailSetupCreate(
                    name=name,
                    smtp_host=cell("smtp_host"),
                    smtp_port=port,
                    smtp_email=email,
                    smtp_password=cell("smtp_password"),
                    smtp_use_tls=_parse_bool(cell("smtp_use_tls"), default=True),
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

            try:
                await self.create(payload)
            except ValueError as exc:
                errors.append(EmailSetupImportRowError(row_number=index, message=str(exc)))
                skipped += 1
                continue
            created += 1

        return EmailSetupImportResult(created=created, skipped=skipped, errors=errors)
