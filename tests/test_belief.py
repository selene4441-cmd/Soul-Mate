from __future__ import annotations

import math

import pytest

from app.core.belief import BetaPosterior, Evidence, confidence_interval, entropy, update


def test_entropy_p0_is_zero() -> None:
    assert entropy(0.0) == 0.0


def test_entropy_p1_is_zero() -> None:
    assert entropy(1.0) == 0.0


def test_entropy_half_is_ln2() -> None:
    assert math.isclose(entropy(0.5), math.log(2.0), rel_tol=0.0, abs_tol=1e-12)


def test_entropy_symmetry() -> None:
    assert math.isclose(entropy(0.2), entropy(0.8), rel_tol=0.0, abs_tol=1e-12)


def test_entropy_rejects_out_of_range_low() -> None:
    with pytest.raises(ValueError):
        entropy(-1e-9)


def test_entropy_rejects_out_of_range_high() -> None:
    with pytest.raises(ValueError):
        entropy(1.0 + 1e-9)


def test_posterior_rejects_non_positive_alpha() -> None:
    with pytest.raises(ValueError):
        BetaPosterior(alpha=0.0, beta=1.0)


def test_posterior_rejects_non_positive_beta() -> None:
    with pytest.raises(ValueError):
        BetaPosterior(alpha=1.0, beta=0.0)


def test_evidence_rejects_negative_positive() -> None:
    with pytest.raises(ValueError):
        Evidence(positive=-1.0, negative=0.0)


def test_evidence_rejects_negative_negative() -> None:
    with pytest.raises(ValueError):
        Evidence(positive=0.0, negative=-1.0)


def test_update_noop_with_zero_evidence() -> None:
    p = BetaPosterior(alpha=1.0, beta=1.0)
    p2 = update(p, Evidence(positive=0.0, negative=0.0))
    assert p2 == p


def test_update_accepts_tuple_evidence() -> None:
    p = BetaPosterior(alpha=2.0, beta=3.0)
    p2 = update(p, (4.0, 5.0))
    assert p2.alpha == 6.0
    assert p2.beta == 8.0


def test_update_increases_mean_with_positive_evidence() -> None:
    p = BetaPosterior(alpha=1.0, beta=4.0)
    p2 = update(p, Evidence(positive=3.0, negative=0.0))
    assert p2.mean > p.mean


def test_update_decreases_mean_with_negative_evidence() -> None:
    p = BetaPosterior(alpha=4.0, beta=1.0)
    p2 = update(p, Evidence(positive=0.0, negative=3.0))
    assert p2.mean < p.mean


def test_ci_bounds_in_unit_interval() -> None:
    lo, hi = confidence_interval(BetaPosterior(alpha=1.0, beta=1.0), level=0.95)
    assert 0.0 <= lo <= 1.0
    assert 0.0 <= hi <= 1.0
    assert lo <= hi


def test_ci_rejects_invalid_level_low() -> None:
    with pytest.raises(ValueError):
        confidence_interval(BetaPosterior(alpha=1.0, beta=1.0), level=0.0)


def test_ci_rejects_invalid_level_high() -> None:
    with pytest.raises(ValueError):
        confidence_interval(BetaPosterior(alpha=1.0, beta=1.0), level=1.0)


def test_ci_shrinks_with_more_evidence_same_mean() -> None:
    lo1, hi1 = confidence_interval(BetaPosterior(alpha=1.0, beta=1.0), level=0.95)
    lo2, hi2 = confidence_interval(BetaPosterior(alpha=20.0, beta=20.0), level=0.95)
    assert (hi2 - lo2) < (hi1 - lo1)


def test_ci_extreme_positive_evidence_near_one() -> None:
    lo, hi = confidence_interval(BetaPosterior(alpha=500.0, beta=1.0), level=0.95)
    assert lo > 0.95
    assert hi > 0.99


def test_entropy_monotone_decrease_with_increasing_supporting_evidence() -> None:
    p = BetaPosterior(alpha=1.0, beta=1.0)
    last_h = entropy(p.mean)
    for _ in range(1, 50):
        p = update(p, (1.0, 0.0))
        h = entropy(p.mean)
        assert h <= last_h + 1e-15
        last_h = h


def test_entropy_monotone_decrease_with_increasing_disconfirming_evidence() -> None:
    p = BetaPosterior(alpha=1.0, beta=1.0)
    last_h = entropy(p.mean)
    for _ in range(1, 50):
        p = update(p, (0.0, 1.0))
        h = entropy(p.mean)
        assert h <= last_h + 1e-15
        last_h = h

