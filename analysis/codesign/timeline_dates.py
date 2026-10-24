"""Dates for the deployment-timeline figure (fig:timeline): what the records date, and how well.

From data/db_extracts/timeline_dives.psv (sql/extract_timeline_dives.sql; one row per dive, 525 dives):
  dives per month         dive_datetime (camera clock); also the dives that hold canonical images
  laser colour            per camera and month, a dive is red or green when >= 90% of its completed laser
                          labels with a dot are that colour (as in redgreen.py); dives without laser labels
                          have no colour. First mostly-green month per camera = first month whose labelled
                          dives are mostly green.
  slate pattern           dive.dive_slate_id: H, tic-tac-toe (TTT 1-6), V-slate/chevron (1-4); share of the
                          dives in each pattern's date span that record a slate
  calibration target      dive.calibration_target_id (the E4E checkerboard)
Undated elements (mount revisions, aluminium mount) come from analysis/codesign/timeline.yaml only.

Writes analysis/codesign/results/timeline_{months,colour_by_camera,slate_coverage}.csv.
Run: uv run python analysis/codesign/timeline_dates.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/results"
COLS = "dive_id dive_datetime camera slate target images red green".split()


def main():
    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None, names=COLS)
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True); D["month"] = D.t.dt.strftime("%Y-%m")
    lab = D.red + D.green
    D["colour"] = np.select([(lab > 0) & (D.green / lab.where(lab > 0) >= 0.9), (lab > 0) & (D.red / lab.where(lab > 0) >= 0.9), lab > 0],
                            ["green", "red", "mixed"], "no laser labels")
    D["pattern"] = np.select([D.slate.fillna("").str.startswith("H"), D.slate.fillna("").str.startswith("Tic"),
                              D.slate.fillna("").str.startswith("V")], ["H", "tic-tac-toe", "chevron (V)"], "")

    M = D.groupby("month").agg(dives=("dive_id", "size"), with_images=("images", lambda s: int((s > 0).sum())),
                               red=("colour", lambda s: int((s == "red").sum())), green=("colour", lambda s: int((s == "green").sum())),
                               mixed=("colour", lambda s: int((s == "mixed").sum())), unlabelled=("colour", lambda s: int((s == "no laser labels").sum())),
                               slate_recorded=("pattern", lambda s: int((s != "").sum())), checkerboard=("target", lambda s: int(s.notna().sum())))
    OUT.mkdir(parents=True, exist_ok=True); M.to_csv(OUT / "timeline_months.csv")

    C = D[D.colour.isin(["red", "green"])].groupby(["camera", "month", "colour"]).size().unstack(fill_value=0)
    C.to_csv(OUT / "timeline_colour_by_camera.csv")
    first = {}
    for cam, g in C.groupby(level=0):
        g = g.droplevel(0)
        gm = g[g.get("green", 0) > g.get("red", 0)]
        first[cam] = dict(first_month=g.index.min(), last_month=g.index.max(), labelled_dives=int(g.values.sum()),
                          first_mostly_green=gm.index.min() if len(gm) else "never",
                          red_after_first_green=int(g.loc[g.index > (gm.index.min() if len(gm) else "9999"), "red"].sum()) if "red" in g else 0)

    spans = {"H": ("2023-08-01", "2023-08-03"), "tic-tac-toe": ("2023-08-29", "2023-11-14"), "chevron (V)": ("2024-03-13", "2024-12-10")}
    S = []
    for p, (a, b) in spans.items():
        w = D[(D.t >= pd.Timestamp(a, tz="UTC")) & (D.t < pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1))]
        S.append(dict(pattern=p, span=f"{a}..{b}", dives_in_span=len(w), dives_recording_this_pattern=int((D.pattern == p).sum()),
                      dives_in_span_recording_any_slate=int((w.pattern != "").sum()),
                      share=(w.pattern != "").mean(), other_patterns_in_span=int(((w.pattern != "") & (w.pattern != p)).sum())))
    S = pd.DataFrame(S); S.to_csv(OUT / "timeline_slate_coverage.csv", index=False, float_format="%.4f")

    cb = D[D.target.notna()]
    pd.set_option("display.width", 220)
    print("Dives:", len(D), D.t.min().date(), "..", D.t.max().date(), "; with canonical images:", int((D.images > 0).sum()))
    print("\nPer month:"); print(M.to_string())
    print("\nLaser colour by camera:"); print(pd.DataFrame(first).T.to_string())
    print("\nSlate coverage:"); print(S.round(3).to_string(index=False))
    print("\nCheckerboard (calibration_target) dives:", len(cb), "dates:", sorted(cb.t.dt.date.astype(str).unique()), "cameras:", sorted(cb.camera.unique()))


if __name__ == "__main__":
    main()
