from datetime import datetime, timedelta, timezone

import pytest

from app.models.intent_signal import IntentSignal
from app.models.intent_signal import IntentSignalType
from app.services.intent_score_service import compute_intent_score, decay_multiplier


def test_decay_multiplier_anchor_points():
    assert decay_multiplier(0) == 1.0
    assert decay_multiplier(2) == 1.0
    assert decay_multiplier(14) == pytest.approx(0.7)
    assert decay_multiplier(30) == pytest.approx(0.3)
    assert decay_multiplier(45) == 0.0
    assert decay_multiplier(100) == 0.0


def test_decay_multiplier_interpolates_between_anchors():
    # Halfway between day 2 (1.0) and day 14 (0.7) -> ~0.85
    assert decay_multiplier(8) == pytest.approx(0.85, abs=0.01)
    # Halfway between day 30 (0.3) and day 45 (0.0) -> ~0.15
    assert decay_multiplier(37.5) == pytest.approx(0.15, abs=0.01)


def _signal(signal_type: IntentSignalType, days_old: float) -> IntentSignal:
    return IntentSignal(
        signal_type=signal_type,
        provider="manual",
        source="test",
        source_url="https://example.com",
        detected_at=datetime.now(timezone.utc) - timedelta(days=days_old),
    )


def test_compute_intent_score_fresh_service_request():
    signals = [_signal(IntentSignalType.SERVICE_REQUEST, days_old=0)]
    assert compute_intent_score(signals) == 30


def test_compute_intent_score_decays_with_age():
    fresh = compute_intent_score([_signal(IntentSignalType.HIRING, days_old=0)])
    old = compute_intent_score([_signal(IntentSignalType.HIRING, days_old=30)])
    ancient = compute_intent_score([_signal(IntentSignalType.HIRING, days_old=60)])
    assert fresh > old > ancient
    assert ancient == 0


def test_compute_intent_score_sums_multiple_signals_and_caps_at_100():
    signals = [
        _signal(IntentSignalType.SERVICE_REQUEST, days_old=0),
        _signal(IntentSignalType.FUNDING, days_old=0),
        _signal(IntentSignalType.HIRING, days_old=0),
        _signal(IntentSignalType.EXPANSION, days_old=0),
        _signal(IntentSignalType.PRODUCT_LAUNCH, days_old=0),
    ]
    # 30+20+15+15+12 = 92, under the cap
    assert compute_intent_score(signals) == 92

    signals_over_cap = signals + [_signal(IntentSignalType.ASKING_FOR_RECOMMENDATION, days_old=0)]
    assert compute_intent_score(signals_over_cap) == 100


def test_compute_intent_score_unknown_type_uses_other_weight():
    # OTHER weight is 2 — used as the fallback for any type missing from weights
    from app.services.intent_score_service import DEFAULT_SIGNAL_WEIGHTS

    assert compute_intent_score([_signal(IntentSignalType.OTHER, days_old=0)]) == DEFAULT_SIGNAL_WEIGHTS[
        IntentSignalType.OTHER
    ]


def test_compute_intent_score_no_signals_is_zero():
    assert compute_intent_score([]) == 0
