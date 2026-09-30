"""Pins the head/tail cross-domain numbers (T4) and the fork decomposition (T5)."""

import numpy as np
import pytest

from fishsense_cscw import headtail as ht


def test_mobile_reproduces_the_source_notebook():
    """Frozen data reproduces 2026-07-18_fishsense-core-test/validation.ipynb section 6."""
    p = ht.load_mobile("v2_1_5")
    p = p[p.predicted]
    assert len(p) == 148
    assert p.snout_px.median() == pytest.approx(16.51, abs=0.01)
    assert p.fork_px.median() == pytest.approx(31.57, abs=0.01)


def test_lite_frozen_run_is_the_167_frame_field_set():
    for model, n_pred in (("fishial", 90), ("sam3", 117)):
        df = ht.load_lite(model)
        assert len(df) == 167 and df.predicted.sum() == n_pred
        assert df.dive_id.nunique() == 6
        assert df.length_px.notna().all()  # from the manifest, so unpredicted frames too


def test_cross_domain_headline():
    mob = ht.summarize(ht.load_mobile())
    lite = ht.summarize(ht.load_lite("fishial"), cluster="dive_id")
    # Snout is domain-invariant in % of length; fork is not.
    assert mob["snout_pct_p50"] == pytest.approx(1.74, abs=0.02)
    assert lite["snout_pct_p50"] == pytest.approx(2.66, abs=0.02)
    assert mob["fork_pct_p50"] == pytest.approx(4.79, abs=0.02)
    assert lite["fork_pct_p50"] == pytest.approx(8.99, abs=0.02)
    # Mobile reads long; Lite does not.
    assert mob["signed_length_err_pct_p50"] == pytest.approx(2.0, abs=0.05)
    assert abs(lite["signed_length_err_pct_p50"]) < 0.5
    assert mob["coverage_pct"] == pytest.approx(98.0, abs=0.1)
    assert lite["coverage_pct"] == pytest.approx(53.9, abs=0.1)


def test_the_domains_do_not_overlap_in_fish_size_at_the_segmenter():
    """Why coverage cannot be attributed to domain: the Mobile fish reaches the
    segmenter ~4x larger. If this ever stops holding, the T4 caveat must be revisited."""
    mob = ht.load_mobile()
    lite = ht.load_lite("fishial")
    assert mob.model_input_px.median() / lite.model_input_px.median() > 3.5


def test_fork_error_is_lateral_not_a_constant_offset():
    """T5 on Mobile: the answer to headtail-prediction.md section 9.2."""
    d = ht.fork_decomposition(ht.load_mobile())
    assert len(d) == 148
    along, across = d.fork_along_pct.median(), d.fork_across_pct.median()
    assert 0.5 < along < 1.2  # small, systematic overshoot past the notch...
    assert across > 3 * along  # ...but the typical error is sideways
    total = np.hypot(d.fork_along_pct, d.fork_across_pct)
    corrected = np.hypot(d.fork_along_pct - along, d.fork_across_pct)
    assert corrected.median() > 0.9 * total.median()  # a constant offset does not fix it
    assert d.mask_past_fork_pct.median() > 3  # the mask includes the caudal lobes
