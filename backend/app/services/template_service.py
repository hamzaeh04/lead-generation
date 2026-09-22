"""Email template variable rendering (section 41).

Only the fixed, known variable set is ever substituted — anything else in
`{{...}}` is left untouched in the output so an operator notices a typo
rather than having it silently vanish. A known variable with no backing
data renders as an empty string, never a fabricated value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.ai_generation import AIGeneration
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal

SUPPORTED_VARIABLES = (
    "first_name", "last_name", "company_name", "job_title", "city",
    "industry", "website", "personalized_intro", "intent_signal",
    "outreach_angle", "unsubscribe_url",
)

_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def ensure_lead_personalization(subject: str, body: str) -> tuple[str, str]:
    """Guarantee lead name appears in subject and a Hi greeting in the body.

    Operators often paste static copy; when {{first_name}} is missing we inject
    it so every send is personalized from the contact record.
    """
    personalized_subject = subject
    if "{{first_name}}" not in subject and "{{last_name}}" not in subject:
        personalized_subject = f"{{{{first_name}}}}, {subject}" if subject.strip() else "{{first_name}}"

    personalized_body = body
    if "{{first_name}}" not in body:
        personalized_body = f"Hi {{{{first_name}}}},\n\n{body}" if body.strip() else "Hi {{first_name}},"

    return personalized_subject, personalized_body


def build_context(
    *,
    contact: Contact,
    company: Company | None,
    personalization: AIGeneration | None,
    unsubscribe_url: str,
    intent_signal: IntentSignal | None = None,
) -> dict[str, str]:
    context: dict[str, str] = {var: "" for var in SUPPORTED_VARIABLES}
    context["unsubscribe_url"] = unsubscribe_url

    if contact.first_name:
        context["first_name"] = contact.first_name
    if contact.last_name:
        context["last_name"] = contact.last_name
    if contact.job_title:
        context["job_title"] = contact.job_title
    if company:
        if company.name:
            context["company_name"] = company.name
        if company.city:
            context["city"] = company.city
        if company.industry:
            context["industry"] = company.industry
        if company.website:
            context["website"] = company.website
    if personalization:
        if personalization.opening_line:
            context["personalized_intro"] = personalization.opening_line
        if personalization.outreach_angle:
            context["outreach_angle"] = personalization.outreach_angle
        # personalized_intro is derived from the AI generation, which itself
        # only ever used real source data (see PersonalizationService) — so
        # threading it through here doesn't reintroduce fabrication risk.
    if intent_signal and intent_signal.signal_text:
        context["intent_signal"] = intent_signal.signal_text

    return context


@dataclass(frozen=True, slots=True)
class RenderedTemplate:
    text: str
    variables_used: list[str]
    variables_filled: list[str]
    variables_empty: list[str]
    unrecognized_variables: list[str]


def render_template(template: str, context: dict[str, str]) -> RenderedTemplate:
    variables_used: list[str] = []
    unrecognized: list[str] = []

    def _substitute(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name not in SUPPORTED_VARIABLES:
            unrecognized.append(var_name)
            return match.group(0)
        variables_used.append(var_name)
        return context.get(var_name, "")

    rendered = _VARIABLE_PATTERN.sub(_substitute, template)

    filled = [v for v in variables_used if context.get(v)]
    empty = [v for v in variables_used if not context.get(v)]

    return RenderedTemplate(
        text=rendered,
        variables_used=sorted(set(variables_used)),
        variables_filled=sorted(set(filled)),
        variables_empty=sorted(set(empty)),
        unrecognized_variables=sorted(set(unrecognized)),
    )
