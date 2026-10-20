import pytest

from bidsmith.estimating.costdata import get_cost_data
from bidsmith.estimating.engine import escalation_factor, estimate, size_factor
from bidsmith.schemas import EstimateInputs


def make_inputs(**overrides) -> EstimateInputs:
    base = dict(
        building_type="office",
        gross_sf=80_000,
        sf_assumed=False,
        state=None,
        quality="typical",
        construction_midpoint_year=2025.5,
    )
    return EstimateInputs(**{**base, **overrides})


def test_csi_splits_sum_to_one():
    for archetype, divisions in get_cost_data().splits.items():
        assert sum(d.pct for d in divisions) == pytest.approx(1.0), archetype


def test_hand_computed_baseline():
    # Typical office at typical size, national location, base-year midpoint: $350/SF exactly.
    est = estimate(make_inputs())
    assert est.size_factor == 1.0
    assert est.location_factor == 1.0
    assert est.escalation_factor == 1.0
    assert est.hard_cost == pytest.approx(350 * 80_000)
    # Class 4 markups: fee 5% + bonds 2% + contingency 10% = 17%
    assert est.total == pytest.approx(350 * 80_000 * 1.17)
    assert sum(line.amount for line in est.lines) == pytest.approx(est.hard_cost, rel=1e-6)


def test_class_and_range_follow_sf_certainty():
    stated = estimate(make_inputs(sf_assumed=False))
    assumed = estimate(make_inputs(sf_assumed=True))
    assert stated.aace_class == 4 and assumed.aace_class == 5
    assert stated.low == pytest.approx(stated.total * 0.8)
    assert stated.high == pytest.approx(stated.total * 1.3)
    assert assumed.low == pytest.approx(assumed.total * 0.7)
    assert assumed.high == pytest.approx(assumed.total * 1.5)
    # Class 5 carries more contingency
    assert assumed.total > stated.total


def test_location_and_premiums_and_design_build():
    est = estimate(make_inputs(state="MN", premiums=["security_hardening"], design_build=True))
    expected_hard = 350 * 1.06 * 1.05 * 80_000
    assert est.hard_cost == pytest.approx(expected_hard)
    assert any("Design fee" in m.name for m in est.markups)


def test_unknown_premium_rejected():
    with pytest.raises(ValueError):
        estimate(make_inputs(premiums=["gold_plating"]))


def test_escalation_compounds_partial_years():
    rates = {2025: 0.04, 2026: 0.04}
    assert escalation_factor(2025.5, rates) == 1.0
    assert escalation_factor(2026.5, rates) == pytest.approx(1.04)
    assert escalation_factor(2026.0, rates) == pytest.approx(1.04**0.5)


def test_size_factor_is_bounded():
    assert size_factor(1_000, 100_000) == 1.25
    assert size_factor(10_000_000, 100_000) == 0.85
    assert size_factor(50_000, 100_000) > 1.0
