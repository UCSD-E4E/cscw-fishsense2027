"""Per-month dive counts behind fig:timeline, by laser color and by slate pattern, and how many dives without a
recorded pattern have a slate frame in which the pattern could be identified.

Per dive: analysis/codesign/timeline_dives.py (laser color and slate pattern, each with its source).
Slate frames in dives without a recorded pattern, from the slate-presence detector (sibling repo
../2026-10-03_slate_detector, read by relative path):
  human     data/manifest.csv label == slate (Label Studio answers in the v1 backup, plus its manual queues)
  detector  runs/scan/predictions.csv p_slate >= 0.5 (EfficientNet-B0 presence classifier; its
            runs/cv-q1/cv_report.json gives dive-grouped cross-validation precision and recall)
The detector says whether a slate is in the frame, not which pattern; the pattern would still have to be read
(by eye or by template matching against data/templates/*.pdf, which no code does yet).

Writes analysis/codesign/results/timeline_counts_by_month.csv and timeline_slate_frame_coverage.csv.
Run: uv run python analysis/codesign/timeline_counts.py
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import timeline_dives as T  # noqa: E402

RES = REPO / "analysis/codesign/results"
SD = REPO.parent / "2026-10-03_slate_detector"
MONTHS = pd.period_range("2023-08", "2025-01", freq="M")


def main():
    D = T.load()
    n = D.groupby("month").size().reindex(MONTHS, fill_value=0).rename("dives")
    L = D.groupby(["month", "laser"]).size().unstack(fill_value=0).reindex(MONTHS, fill_value=0)
    nolab = (D.red + D.green == 0).groupby(D.month).sum().reindex(MONTHS, fill_value=0).rename("no_laser_labels")
    P = D.assign(pattern=D.pattern.fillna("unrecorded")).groupby(["month", "pattern"]).size().unstack(fill_value=0).reindex(MONTHS, fill_value=0)
    P = P.reindex(columns=["H", "tic-tac-toe", "chevron", "unrecorded"], fill_value=0)
    src = D.groupby(["month", "pattern_source"]).size().unstack(fill_value=0).reindex(MONTHS, fill_value=0).add_prefix("pattern_from_")

    U = D[D.pattern.isna() & (D.images > 0)]
    man = pd.read_csv(SD / "data/manifest.csv")
    human = set(man[(man.label == "slate") & man.dive_id.isin(U.dive_id)].dive_id)
    scan = pd.read_csv(SD / "runs/scan/predictions.csv")
    scanned = set(scan[scan.dive_id.isin(U.dive_id)].dive_id)
    det = set(scan[(scan.p_slate >= 0.5) & scan.dive_id.isin(U.dive_id)].dive_id)
    either = human | det
    U = U.assign(human=U.dive_id.isin(human), detector=U.dive_id.isin(det), any_slate_frame=U.dive_id.isin(either))
    cov = U.groupby("month")[["human", "detector", "any_slate_frame"]].sum().reindex(MONTHS, fill_value=0)
    cov.insert(0, "unrecorded_with_images", U.groupby("month").size().reindex(MONTHS, fill_value=0))

    X = pd.concat([n, L[["red", "green"]], nolab, P, src, cov], axis=1)
    X["recorded_share"] = (X[["H", "tic-tac-toe", "chevron"]].sum(axis=1) / X.dives.where(X.dives > 0)).round(3)
    RES.mkdir(parents=True, exist_ok=True)
    X.to_csv(RES / "timeline_counts_by_month.csv", index_label="month")

    cv = json.load(open(SD / "runs/cv-q1/cv_report.json"))["overall"]
    C = pd.DataFrame([
        dict(quantity="dives", value=len(D)),
        dict(quantity="dives with a recorded pattern", value=int(D.pattern.notna().sum())),
        dict(quantity="dives without a recorded pattern", value=int(D.pattern.isna().sum())),
        dict(quantity="... of which hold their own images", value=len(U)),
        dict(quantity="... scanned by the detector", value=len(scanned)),
        dict(quantity="... with a human-labeled slate frame", value=len(human)),
        dict(quantity="... with a detector slate frame (p >= 0.5)", value=len(det)),
        dict(quantity="... with either", value=len(either)),
        dict(quantity="... imageless duplicates of those (would inherit)", value=int(pd.read_csv(REPO / "data/db_extracts/duplicate_dives.psv", sep="|", header=None, names=["d", "s", "n"]).query("s in @either").d.nunique())),
        dict(quantity="detector CV frames", value=cv["n"]), dict(quantity="detector CV precision", value=round(cv["precision"], 4)),
        dict(quantity="detector CV recall", value=round(cv["recall"], 4)), dict(quantity="detector CV false positives", value=cv["false_positives"]),
    ])
    C.to_csv(RES / "timeline_slate_frame_coverage.csv", index=False)
    pd.set_option("display.width", 250)
    print(X.to_string()); print(); print(C.to_string(index=False))


if __name__ == "__main__":
    main()
