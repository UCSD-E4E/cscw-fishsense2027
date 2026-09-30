"""Pins the REEF turnaround: years from dive to measurable, and many dives never got there."""

import pytest

from fishsense_cscw import turnaround as ta


def test_reef_turnaround():
    w = ta.reef_dives()
    assert len(w) == 243
    assert w.measurable_days.notna().sum() == 138
    assert w.measurable_days.median() == pytest.approx(773, abs=2)
    assert w.to_lab_days.median() == pytest.approx(227, abs=2)
    assert w.in_lab_days.median() == pytest.approx(521, abs=2)


def test_many_reef_dives_never_became_measurable():
    w = ta.reef_dives()
    assert w.measurable_days.isna().sum() == 105  # 43 % as of the 2026-09-25 backup
