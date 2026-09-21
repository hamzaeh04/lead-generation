"""LeadScore: a sales rep's per-contact prioritization score.

Distinct from ICPScore and IntentScore (both company-level): this answers
"which contact should I call next," not "is this the right company." It
blends five signals a rep actually weighs when triaging a pipeline:

  - icp_fit       (30) — is this the right kind of company (reuses ICPScore)
  - intent        (25) — are they showing buying signals right now (reuses
                          IntentScore)
  - authority     (20) — can THIS person actually say yes (title match
                          against the ICP's target titles, falling back to
                          a generic seniority tier)
  - reachability  (15) — can we actually get in touch (has an email on file
                          or not)
  - engagement    (10) — have they already responded (a "replied" contact
                          outranks a cold "new" one almost regardless of
                          the above)

A disqualified contact (bounced/unsubscribed/lost) always scores 0 — no
value in prioritizing a dead lead, no matter how good the company fit is.
"""
from __future__ import annotations

from app.models.contact import Contact, LeadStatus
from app.models.icp_profile import ICPProfile

DEFAULT_WEIGHTS: dict[str, int] = {
    "icp_fit": 30,
    "intent": 25,
    "authority": 20,
    "reachability": 15,
    "engagement": 10,
}

_DISQUALIFIED_STATUSES = {LeadStatus.LOST, LeadStatus.UNSUBSCRIBED, LeadStatus.BOUNCED}

# Generic seniority fallback when the contact's title doesn't match the
# ICP's explicit target_titles (or no ICP profile was given at all).
_SENIORITY_TIERS: dict[str, float] = {
    "owner": 1.0,
    "founder": 1.0,
    "c_suite": 1.0,
    "executive": 1.0,
    "vp": 0.7,
    "director": 0.7,
    "manager": 0.4,
    "senior": 0.2,
    "entry": 0.1,
    "individual_contributor": 0.1,
}

# How far through the outreach pipeline a contact has already gotten.
_ENGAGEMENT_TIERS: dict[LeadStatus, float] = {
    LeadStatus.NEW: 0.0,
    LeadStatus.VERIFIED: 0.1,
    LeadStatus.READY_FOR_OUTREACH: 0.2,
    LeadStatus.CONTACTED: 0.4,
    LeadStatus.OPENED: 0.5,
    LeadStatus.CLICKED: 0.6,
    LeadStatus.REPLIED: 0.9,
    LeadStatus.INTERESTED: 1.0,
    LeadStatus.MEETING: 1.0,
    LeadStatus.WON: 1.0,
}


def _authority_score(contact: Contact, icp: ICPProfile | None) -> tuple[float, str | None]:
    if not contact.job_title:
        return 0.0, None
    title = contact.job_title.strip().lower()

    if icp and icp.target_titles:
        targets = [t.strip().lower() for t in icp.target_titles]
        if any(t == title or t in title for t in targets):
            return 1.0, f"title matches target ({contact.job_title})"

    if contact.seniority:
        fraction = _SENIORITY_TIERS.get(contact.seniority.strip().lower())
        if fraction:
            return fraction, f"seniority: {contact.seniority}"

    return 0.0, None


def _reachability_score(contact: Contact) -> tuple[float, str | None]:
    if contact.email:
        return 1.0, "has email on file"
    return 0.0, None


def _engagement_score(contact: Contact) -> tuple[float, str | None]:
    fraction = _ENGAGEMENT_TIERS.get(contact.status, 0.0)
    if fraction > 0:
        return fraction, f"engagement stage: {contact.status.replace('_', ' ')}"
    return 0.0, None


def compute_lead_score(
    *,
    contact: Contact,
    icp_score: int | None,
    intent_score: int,
    icp: ICPProfile | None,
    weights: dict[str, int] | None = None,
) -> tuple[int, list[str]]:
    weights = weights or DEFAULT_WEIGHTS

    if contact.status in _DISQUALIFIED_STATUSES:
        return 0, [f"disqualified: contact status is {contact.status}"]

    breakdown: list[str] = []
    total = 0.0

    icp_fraction = (icp_score or 0) / 100
    total += weights["icp_fit"] * icp_fraction
    if icp_score is not None:
        breakdown.append(f"company ICP fit: {icp_score}/100")

    intent_fraction = intent_score / 100
    total += weights["intent"] * intent_fraction
    if intent_score > 0:
        breakdown.append(f"company intent: {intent_score}/100")

    authority_fraction, authority_note = _authority_score(contact, icp)
    total += weights["authority"] * authority_fraction
    if authority_note:
        breakdown.append(authority_note)

    reachability_fraction, reachability_note = _reachability_score(contact)
    total += weights["reachability"] * reachability_fraction
    if reachability_note:
        breakdown.append(reachability_note)

    engagement_fraction, engagement_note = _engagement_score(contact)
    total += weights["engagement"] * engagement_fraction
    if engagement_note:
        breakdown.append(engagement_note)

    return min(round(total), 100), breakdown
