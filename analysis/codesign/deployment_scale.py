"""Deployment scale for the SenSys paper: counts only, nothing that names a person, place or organization.

Field = canonical records of physical dives (physical_dives.py) outside the FishSense test deployments 2, 3 and 4
(timeline_dives.TEST_DEPLOYMENTS), as calibration_trust.py. Cameras = distinct devices (data/fishsense_api/
missions_lab.csv device_name) on field dives; period = first and last capture of their canonical images
(data/db_extracts/dive_effort.psv, camera clock).
Labelers and labels (data/db_extracts/labeler_counts.psv, sql/extract_labeler_counts.sql): every non-cancelled Label
Studio annotation on laser, head/tail, species and slate labels in the frozen 2026-09-25 snapshot (all dives, pool and
test included); labelers = distinct Label Studio user ids.
Person-hours:
  recorded   sum of Label Studio lead_time (time a task was open, so idle tabs count), capped at 300 s per annotation,
             and uncapped; annotations without a lead_time add nothing
  estimated  sum over field physical dives of dive_time.py --physical's estimate (frames x per-task median seconds
             drawn without a pre-fill; results/dive_time_dives_physical.csv), all field dives incl. implausible spans
Not recorded anywhere this repo reads: who dove (no diver field), dive sites as a structured field (only free-text
folder names), and regions (the snapshot has none; the services API's regions are reported by the author separately).
Writes analysis/codesign/results/deployment_scale.csv.
Run: uv run python analysis/codesign/deployment_scale.py
"""
from __future__ import annotations

import sys

import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import physical_dives as PD  # noqa: E402
import timeline_dives as T  # noqa: E402

RES = REPO / "analysis/codesign/results"


def main():
    K = PD.load().set_index("dive_id")
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv").set_index("dive_id")
    canon = K.index[K.kind == "canonical"]
    field = [d for d in canon if M.loc[d, "deployment_number"] not in T.TEST_DEPLOYMENTS]
    E = pd.read_csv(REPO / "data/db_extracts/dive_effort.psv", sep="|", header=None, usecols=[0, 3, 4], names=["dive_id", "first", "last"])
    E["first"], E["last"] = pd.to_datetime(E["first"], utc=True), pd.to_datetime(E["last"], utc=True)
    recs = K.index[K.physical_dive.isin(field)]                      # every record of a field physical dive
    Ef = E[E.dive_id.isin(recs)]
    rows = [dict(item="field physical dives", value=len(field), note="canonical records outside test deployments 2-4"),
            dict(item="cameras (units) used on field dives", value=M.loc[field, "device_name"].nunique(), note="distinct devices"),
            dict(item="field capture period", value=f"{Ef['first'].min():%Y-%m-%d} .. {Ef['last'].max():%Y-%m-%d}", note="camera clock"),
            dict(item="field deployments", value=M.loc[field, "deployment_number"].nunique(), note="")]
    L = pd.read_csv(REPO / "data/db_extracts/labeler_counts.psv", sep="|", header=None,
                    names=["kind", "annotations", "labelers", "lead_s", "capped_s", "with_lead", "first", "last"]).set_index("kind")
    for k in ("all", "laser", "headtail", "species", "slate"):
        r = L.loc[k]
        rows.append(dict(item=f"labels: {k}", value=int(r.annotations), note=f"{int(r.labelers)} labelers; {r['first']} .. {r['last']}"))
    a = L.loc["all"]
    rows.append(dict(item="person-hours recorded, capped 300 s", value=round(a.capped_s / 3600, 1),
                     note=f"{int(a.with_lead)} of {int(a.annotations)} annotations carry a lead_time; uncapped {a.lead_s / 3600:,.0f} h"))
    D = pd.read_csv(RES / "dive_time_dives_physical.csv")
    Df = D[D.dive_id.isin(field)]
    rows.append(dict(item="person-hours estimated, field dives", value=round(Df.human_est_h.sum(), 1),
                     note=f"{len(Df)} field physical dives with a dive_time row"))
    R = pd.DataFrame(rows); R.to_csv(RES / "deployment_scale.csv", index=False)
    pd.set_option("display.width", 200, "display.max_colwidth", 100)
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
