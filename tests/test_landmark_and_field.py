"""Pins the landmark-noise bound (T6) and the field frames/range figures (T7a/b).

Both read the IMWUT repo in place, so both skip if it is not checked out beside this one.
If the IMWUT corpus is re-pulled these may move -- that is the point of pinning them.
"""

import pytest

from fishsense_cscw.paths import IMWUT

pytestmark = pytest.mark.skipif(not IMWUT.is_dir(), reason="needs ../imwut_2026_fishsense_lite")


def test_landmark_bound_is_stable_across_binning():
    from fishsense_cscw import landmark as lm

    df = lm.load_cohort()
    assert len(df) == 1051
    primary = lm.noise_cells(df, 0.25, 6)
    assert len(primary) == 39 and primary.dive_id.nunique() == 6
    assert primary.bound_pct.median() == pytest.approx(0.56, abs=0.02)
    assert primary.px_per_endpoint.median() == pytest.approx(2.0, abs=0.1)
    for bin_m in (0.15, 0.25, 0.5):
        assert 0.5 < lm.noise_cells(df, bin_m, 5).bound_pct.median() < 0.8


def test_field_frames_per_animal():
    from fishsense_cscw import field

    per = field.frames_per_animal(field.load_field())
    assert per.sum() == 162 and len(per) == 73
    assert per.median() == 2 and per.max() == 8
    assert (per == 1).sum() == 31
    assert (per >= field.FRAMES_FOR_STABLE_P90).sum() == 0


def test_field_range():
    from fishsense_cscw import field

    r = field.range_bands(field.load_field())
    assert r["n"] == 162
    assert r["p50"] == pytest.approx(1.49, abs=0.01)
    assert r["below_1m"] == 35
    assert r["in_table1_range"] == 43
