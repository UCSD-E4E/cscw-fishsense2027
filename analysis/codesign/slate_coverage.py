"""How many physical dives with a slate frame had the slate's template (its scan) recorded, in the frozen 2026-09-25
dump.

Denominator: physical dives (physical_dives.py) with at least one human-labeled slate frame in the slate-presence
classifier's manifest (data/slate_detector/manifest.csv, label 1). Numerator: those whose physical dive has a
record with dive.dive_slate_id set (data/db_extracts/dive_slate_template.psv, sql/extract_dive_slate_template.sql).
95% interval resampling physical dives (2,000 draws, seed 0). Reported for all records and for field dives
(FishSense deployments 2, 3, 4 excluded, timeline_dives.TEST_DEPLOYMENTS).

This is the archive before the 2026-10-27 template assignment in fishsense-services (109 missions given a
template; 62 from the author's V-Slate answers, 47 from an unchecked automatic Tic-Tac-Toe vote; 36 -> 145 of the
lab's 525 missions). That assignment lives in the services database, not in this dump, so it is not counted here.

Writes analysis/codesign/results/slate_coverage.csv.
Run: uv run python analysis/codesign/slate_coverage.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import physical_dives as PD  # noqa: E402
import timeline_dives as T  # noqa: E402


def main():
    phys = PD.physical()
    tpl = pd.read_csv(REPO / "data/db_extracts/dive_slate_template.psv", sep="|", header=None, names=["dive_id", "has", "tid"])
    tpl = tpl.set_index("dive_id").has.eq("t").groupby(phys).any()
    m = pd.read_csv(REPO / "data/slate_detector/manifest.csv")
    slate = pd.Series(sorted(m[m.label == 1].dive_id.map(phys).unique()))
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv")
    test = set(M.dive_id[M.deployment_number.isin(T.TEST_DEPLOYMENTS)].map(phys))
    rng = np.random.default_rng(0)
    rows = []
    for name, ids in (("all", slate), ("field", slate[~slate.isin(test)])):
        k = tpl.reindex(ids).fillna(False).to_numpy(bool)
        b = [rng.choice(k, len(k)).mean() for _ in range(2000)]
        lo, hi = np.percentile(b, [2.5, 97.5])
        rows.append(dict(population=name, physical_dives_with_slate_frame=len(k), with_template=int(k.sum()),
                         share=k.mean(), ci_lo=lo, ci_hi=hi))
        print(f"{name}: {k.sum()} of {len(k)} physical dives with a labeled slate frame have a recorded slate template "
              f"({100 * k.mean():.1f}%, 95% CI {100 * lo:.1f}-{100 * hi:.1f}%)")
    pd.DataFrame(rows).to_csv(REPO / "analysis/codesign/results/slate_coverage.csv", index=False)


if __name__ == "__main__":
    main()
