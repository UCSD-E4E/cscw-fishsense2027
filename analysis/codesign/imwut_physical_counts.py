"""The FishSense Lite (IMWUT) paper's corpus counts, by dive record and by physical dive.

The paper (Sections/evaluation_setup.tex, main.tex) says eleven units recorded 525 dives, 47 of which have
measurements. Those are dive records; analysis/codesign/physical_dives.py maps each record to its physical dive
(re-imports and fragments counted once). Units: the cameras of the records (data/db_extracts/dive_checksums.psv
dive_camera_id; data/db_extracts/timeline_dives.psv camera name). Measurements: data/db_extracts/dive_measurements.psv
(sql/extract_dive_measurements.sql). Field dives exclude the lab's pool and test deployments 2, 3, 4.

Writes analysis/codesign/results/imwut_physical_counts.csv.
Run: uv run python analysis/codesign/imwut_physical_counts.py
"""
from __future__ import annotations

import sys

import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import physical_dives as PD  # noqa: E402
import timeline_dives as T  # noqa: E402

DB = REPO / "data/db_extracts"


def main():
    X = PD.load()
    cam = pd.read_csv(DB / "timeline_dives.psv", sep="|", header=None, usecols=[0, 2], names=["dive_id", "camera"])
    dep = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv")[["dive_id", "deployment_number"]]
    meas = pd.read_csv(DB / "dive_measurements.psv", sep="|", header=None, names=["dive_id", "measurements", "images", "fish"])
    X = X.merge(cam, on="dive_id").merge(dep, on="dive_id", how="left").merge(meas, on="dive_id", how="left")
    X["field"] = ~X.deployment_number.isin(T.TEST_DEPLOYMENTS)
    M = X[X.measurements.notna()]
    rows = []
    def add(q, records, physical):
        rows.append(dict(quantity=q, records=records, physical_dives=physical))
    add("dives", len(X), X.physical_dive.nunique())
    add("dives, field (excluding deployments 2, 3, 4)", int(X.field.sum()), X[X.field].physical_dive.nunique())
    add("dives with measurements", len(M), M.physical_dive.nunique())
    add("dives with measurements, field", int(M.field.sum()), M[M.field].physical_dive.nunique())
    add("units (cameras)", X.camera.nunique(), X[X.kind == "canonical"].camera.nunique())
    add("units with measurements", M.camera.nunique(), M[M.kind == "canonical"].camera.nunique() if (M.kind == "canonical").all() else M.camera.nunique())
    add("measurements", int(M.measurements.sum()), int(M.measurements.sum()))
    R = pd.DataFrame(rows)
    R.to_csv(REPO / "analysis/codesign/results/imwut_physical_counts.csv", index=False)
    print(R.to_string(index=False))
    print("measured records by kind:", M.kind.value_counts().to_dict())
    print("measured physical dives holding 2+ measured records:", M.groupby("physical_dive").size().loc[lambda s: s > 1].to_dict())
    print("cameras:", sorted(X.camera.dropna().unique()))


if __name__ == "__main__":
    main()
