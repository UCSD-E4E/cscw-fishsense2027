"""Pins the E1g coverage estimate: how many dives could calibrate from their own dots.

Reads data/coverage/result_*.csv, written by fishsense_cscw.coverage.coverage() (about 10
minutes per configuration). Regenerate those files, not these numbers, if inputs change.
"""
import numpy as np
import pandas as pd

from fishsense_cscw import coverage as cv
from fishsense_cscw.paths import DATA


def res(name):
    return pd.read_csv(DATA / "coverage" / f"result_{name}.csv")


def counts(c):
    return c.cls.value_counts().reindex(cv.LABELS).fillna(0).astype(int).tolist()


def test_per_dive_coverage():
    c = res("dive_1.00")
    assert len(c) == 255
    assert counts(c) == [21, 167, 67]


def test_pooling_lifts_the_top_tier_and_shrinks_the_bottom():
    c = res("pooled_1.00")
    assert counts(c) == [54, 166, 35]
    assert c.unit.nunique() == 179


def test_failures_are_the_dives_with_few_dots():
    c = res("dive_1.00")
    no = c[c.cls == cv.LABELS[2]]
    assert (100 * no.dive_dots.sum() / c.dive_dots.sum()) < 7  # the failing dives hold ~6 % of dots


def test_simulation_is_deterministic():
    z = np.linspace(0.8, 3.0, 60)
    assert cv.predicted_error(z, trials=5, seed=7) == cv.predicted_error(z, trials=5, seed=7)
