"""IntentScore: configurable per-signal-type weights + time decay.

Score = sum(weight(signal_type) * decay(age_days)) over a company's
signals, capped at 100. Decay follows the anchor points from section 34
(2 days old = 100%, 14 days = 70%, 30 days = 30%, 45+ days = 0%),
interpolated linearly between them — not a hard cliff, so a signal from
day 13 doesn't score wildly differently from day 15.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.intent_signal import IntentSignal
from app.models.intent_signal import IntentSignalType

DEFAULT_SIGNAL_WEIGHTS: dict[IntentSignalType, int] = {
    IntentSignalType.SERVICE_REQUEST: 30,
    IntentSignalType.ASKING_FOR_RECOMMENDATION: 25,
    IntentSignalType.RECENT_POST: 20,
    IntentSignalType.FUNDING: 20,
    IntentSignalType.FUNDING_ANNOUNCEMENT: 20,
    IntentSignalType.HIRING: 15,
    IntentSignalType.NEW_JOB_POST: 15,
    IntentSignalType.EXPANSION: 15,
    IntentSignalType.PRODUCT_LAUNCH: 12,
    IntentSignalType.NEW_LOCATION: 12,
    IntentSignalType.JOB_CHANGE: 10,
    IntentSignalType.NEW_COMPANY: 10,
    IntentSignalType.TECHNOLOGY_CHANGE: 10,
    IntentSignalType.COMPANY_GROWTH: 10,
    IntentSignalType.COMPETITOR_MENTION: 8,
    IntentSignalType.ENGAGEMENT_WITH_RELEVANT_CONTENT: 8,
    IntentSignalType.EVENT_ATTENDANCE: 8,
    IntentSignalType.NEGATIVE_REVIEW: 5,
    IntentSignalType.OTHER: 2,
}

# (age_in_days, multiplier) anchor points, linearly interpolated between them.
_DECAY_POINTS: list[tuple[float, float]] = [(0.0, 1.0), (2.0, 1.0), (14.0, 0.7), (30.0, 0.3), (45.0, 0.0)]


def decay_multiplier(age_days: float) -> float:
    if age_days <= _DECAY_POINTS[0][0]:
        return _DECAY_POINTS[0][1]
    if age_days >= _DECAY_POINTS[-1][0]:
        return 0.0
    for (x0, y0), (x1, y1) in zip(_DECAY_POINTS, _DECAY_POINTS[1:]):
        if x0 <= age_days <= x1:
            if x1 == x0:
                return y0
            t = (age_days - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 0.0


def compute_intent_score(
    signals: list[IntentSignal], *, weights: dict[IntentSignalType, int] | None = None
) -> int:
    weights = weights or DEFAULT_SIGNAL_WEIGHTS
    now = datetime.now(timezone.utc)
    total = 0.0
    for signal in signals:
        weight = weights.get(signal.signal_type, DEFAULT_SIGNAL_WEIGHTS[IntentSignalType.OTHER])
        detected_at = signal.detected_at
        if detected_at.tzinfo is None:
            detected_at = detected_at.replace(tzinfo=timezone.utc)
        age_days = max((now - detected_at).total_seconds() / 86400, 0.0)
        total += weight * decay_multiplier(age_days)
    return min(round(total), 100)
