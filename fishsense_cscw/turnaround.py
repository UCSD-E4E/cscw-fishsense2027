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

--physical: each physical dive counted once (analysis/codesign/physical_dives.py). After the arrival date is read
from each record's folder name, records take the dive id of the record standing for their physical dive, and a
physical dive's capture time and arrival at the lab are the earliest over its records (a re-import's later data
dump is not a second arrival), and its first-label and 90 % times per kind the earliest over its records, which is
approximate for "measurable": a record's 90 % time covers only that record's images. Run as a script, writes
analysis/codesign/results/turnaround_reef_dives.csv and turnaround_summary.csv (fig2a's waiting population:
median days to the lab, dive-resampled 95 % interval), with a _physical suffix under --physical; fig2a
(figures/make_figures.py) is not redrawn.
Run: uv run python -m fishsense_cscw.turnaround [--physical]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import DATA, REPO

TIMESTAMPS = DATA / "turnaround" / "label_timestamps.csv"
OUT = REPO / "analysis/codesign/results"
N_BOOT = 2000
PHYSICAL = "--physical" in sys.argv
SUFFIX = "_physical" if PHYSICAL else ""


def to_physical(t: pd.DataFrame) -> pd.DataFrame:
    """Per-record rows (one per dive and label kind) -> one per physical dive and kind, earliest times."""
    sys.path.insert(0, str(REPO / "analysis/codesign"))
    import physical_dives
    t = t.assign(dive_id=t.dive_id.map(physical_dives.physical()))
    t[["dive_datetime", "at_lab"]] = t.groupby("dive_id")[["dive_datetime", "at_lab"]].transform("min")
    return t.groupby(["dive_id", "dive_datetime", "at_lab", "kind"], as_index=False, dropna=False)[["first_t", "p90_t"]].min()


def reef_dives(physical: bool = False) -> pd.DataFrame:
    t = pd.read_csv(TIMESTAMPS)
    for col in ("dive_datetime", "first_t", "p90_t"):
        t[col] = pd.to_datetime(t[col], utc=True, format="ISO8601")
    t = t[t.path.str.contains("REEF|Reef", na=False)].copy()
    date = t.path.str.extract(r"(\d{4}[-.]\d{2}[-.]\d{2})[ .]*(?:REEF|Reef)")[0].str.replace(".", "-", regex=False)
    t["at_lab"] = pd.to_datetime(date, errors="coerce", utc=True)
    if physical:
        t = to_physical(t)
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


def main():
    w = reef_dives(PHYSICAL)
    wait = w.to_lab_days.dropna(); wait = wait[wait >= 0]          # fig2a's population
    rng = np.random.default_rng(0); x = wait.to_numpy()
    lo, hi = np.percentile([np.median(x[rng.integers(0, len(x), len(x))]) for _ in range(N_BOOT)], [2.5, 97.5])
    S = pd.DataFrame([dict(dives=len(w), measurable=int(w.measurable_days.notna().sum()), measurable_median_days=w.measurable_days.median(),
                           wait_dives=len(wait), wait_median_days=wait.median(), wait_ci_lo=lo, wait_ci_hi=hi,
                           in_lab_median_days=w.in_lab_days.median())])
    OUT.mkdir(parents=True, exist_ok=True)
    w.to_csv(OUT / f"turnaround_reef_dives{SUFFIX}.csv", index=False, float_format="%.4f")
    S.to_csv(OUT / f"turnaround_summary{SUFFIX}.csv", index=False, float_format="%.4f")
    print(S.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
