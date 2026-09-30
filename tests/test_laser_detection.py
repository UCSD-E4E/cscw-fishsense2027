"""Pins T3: laser-detector recall against unseeded human dots, production settings."""

import pytest

from fishsense_cscw import laser_detection as ld


@pytest.fixture(scope="module")
def d():
    return ld.load()


def test_run_is_complete(d):
    assert d.image_id.nunique() == 1571 and len(d) == 2792
    assert d.error.isna().all()


def test_detector_always_localizes_so_presence_is_the_confidence(d):
    """Why the threshold matters: every frame gets a point, including the no-dot ones."""
    assert d.pred_x.notna().all()


def test_headline_production_recall(d):
    prod = d[d.condition == "production"]
    s = ld.summarize(prod)
    assert s.dot_frames == 1221 and s.no_dot_frames == 350
    assert s.recall == pytest.approx(0.821, abs=0.002)
    assert s.missed == pytest.approx(0.115, abs=0.002)
    assert s.false_alarm == pytest.approx(0.111, abs=0.002)


def test_green_is_missed_more_than_red(d):
    prod = d[d.condition == "production"]
    g = ld.summarize(prod[prod.wavelength == "green"])
    r = ld.summarize(prod[prod.wavelength == "red"])
    assert g.recall == pytest.approx(0.752, abs=0.002) and r.recall == pytest.approx(0.860, abs=0.002)
    assert g.missed > 3 * r.missed
    lo, hi = ld.dive_bootstrap(prod, n=500)["red_minus_green_ci"]
    assert lo > 0  # the gap survives resampling whole dives


def test_pool_is_harder_than_reef(d):
    prod = d[(d.condition == "production") & (d.wavelength == "red")]
    pool = ld.summarize(prod[prod.environment == "pool"]).recall
    reef = ld.summarize(prod[prod.environment == "reef"]).recall
    assert reef == pytest.approx(0.940, abs=0.002) and pool == pytest.approx(0.736, abs=0.002)


def test_supplying_the_wavelength_helps_green(d):
    green = d[d.wavelength == "green"]
    prod = ld.summarize(green[green.condition == "production"]).recall
    given = ld.summarize(green[green.condition == "given"]).recall
    assert given - prod == pytest.approx(0.038, abs=0.003)


def test_threshold_cannot_trade_missed_for_wrong(d):
    sweep = ld.threshold_sweep(d[d.condition == "production"])
    assert sweep.loc[0.1, "recall"] - sweep.loc[0.5, "recall"] < 0.02
    assert sweep.loc[0.1, "false_alarm"] > 0.25


def test_confident_wrong_is_mostly_a_different_spot(d):
    cw = d[(d.condition == "production") & (d.outcome == "confident-wrong")]
    assert len(cw) == 78
    assert (cw.distance_px > 100).sum() == 57


def test_dive_line_catches_wrong_spots_and_false_alarms(d):
    g = ld.line_gate_effect(d[d.condition == "production"], corridor_px=25.0)
    assert g.loc["confident-wrong", "rejected"] == pytest.approx(0.535, abs=0.01)
    assert g.loc["false-alarm", "rejected"] == pytest.approx(0.842, abs=0.01)
    assert g.loc["found", "rejected"] < 0.10
