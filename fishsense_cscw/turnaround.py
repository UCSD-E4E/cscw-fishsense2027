"""How long a REEF dive took to become measurable -- the friction that preceded REEF's exit.

REEF, the one outside deployment partner, stopped using FishSense Lite because data could
not be processed quickly, citing the per-dive calibration among the reasons, and moved to
a custom-machined parallel dual-laser caliper on a GoPro, which needs no calibration.
(project lead, 2026-09-25; not yet on record from REEF's side.)

A dive counts as "measurable" when 90 % of its images have a first laser label and 90 %
have a first head/tail label. That ignores species labels and calibration, both of which
a measurement also needs, so it is a lower bound on the real turnaround.

Caveats carried into every number: dive dates come from camera clocks; arrival at the lab
is read from the "YYYY-MM-DD REEF Data Dump" folder name, and some dives show labels
before that date, so the split between "before the lab" and "in the lab" is approximate.
2023 dives also waited on a pipeline that was still being built.
"""

from __future__ import annotations

import pandas as pd

from fishsense_cscw.paths import DATA

TIMESTAMPS = DATA / "turnaround" / "label_timestamps.csv"


def reef_dives() -> pd.DataFrame:
    t = pd.read_csv(TIMESTAMPS)
    for col in ("dive_datetime", "first_t", "p90_t"):
        t[col] = pd.to_datetime(t[col], utc=True, format="ISO8601")
    t = t[t.path.str.contains("REEF|Reef", na=False)].copy()
    date = t.path.str.extract(r"(\d{4}[-.]\d{2}[-.]\d{2})[ .]*(?:REEF|Reef)")[0].str.replace(".", "-", regex=False)
    t["at_lab"] = pd.to_datetime(date, errors="coerce", utc=True)
    w = t.pivot_table(index=["dive_id", "dive_datetime", "at_lab"], columns="kind",
                      values=["first_t", "p90_t"], aggfunc="first")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w.reset_index()
    days = lambda a, b: (a - b).dt.total_seconds() / 86400
    w["to_lab_days"] = days(w.at_lab, w.dive_datetime)
    w["laser_done_days"] = days(w.p90_t_laser, w.dive_datetime)
    w["headtail_done_days"] = days(w["p90_t_headtail"], w.dive_datetime) if "p90_t_headtail" in w else float("nan")
    w["measurable_days"] = w[["laser_done_days", "headtail_done_days"]].max(axis=1, skipna=False)
    w["in_lab_days"] = w.measurable_days - w.to_lab_days
    # a dive "arriving" more than a day before it was shot is a camera-clock error
    return w[(w.to_lab_days >= -1) | w.to_lab_days.isna()]
