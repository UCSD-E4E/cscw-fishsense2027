"""Pins E1: laser calibration with nobody labelling, under production's own refusal gates.

Reads calibration_analysis/e1_label_free/gated_results.csv, written by the gated pass of
e1.py (which needs P4's environment: OpenCV + fishsense_core). Regenerate that file, not
these numbers, if the inputs change.
"""
import pandas as pd
import pytest

from fishsense_cscw.paths import REPO

R = pd.read_csv(REPO / "calibration_analysis" / "e1_label_free" / "gated_results.csv")
S1, S2, S3 = "1 human corners+dots", "2 human corners, detector dots", "3 predicted corners (ECC>=0.8), detector dots"


def cell(kind, stage):
    return R[(R.kind == kind) & (R.stage == stage)]


def test_checkerboard_calibration_is_fully_label_free():
    g = cell("checkerboard", S3)
    assert len(g) == 11 and (g.A == "accepted").all()
    assert (g.worst <= 2).all()  # no silent failures
    assert g.med.median() == pytest.approx(cell("checkerboard", S1).med.median(), abs=0.01)


def test_detector_dots_replace_human_dots_and_fail_closed():
    g = cell("slate", S2)
    acc = g[g.A == "accepted"]
    assert len(acc) == 9 and (g.A != "accepted").sum() == 3
    assert (acc.worst <= 2).all()


def test_predicted_slate_corners_are_the_weak_link():
    g = cell("slate", S3)
    acc = g[g.A == "accepted"]
    assert len(acc) == 6
    assert sorted(acc[acc.worst > 2].dive) == [62, 436]  # 436 is V-Slate 2, a family the predictor does not support
