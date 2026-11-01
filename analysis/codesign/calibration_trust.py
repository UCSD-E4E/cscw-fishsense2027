"""§7 counts on laser calibrations: v1's refusals, the slate-pose fit's refusals, recorded beam moves, and borrowing.

Units are physical dives (physical_dives.py): a record counts for the physical dive it belongs to, and a physical dive
counts once (its outcome taken from its canonical record). "Field" is the timeline's population: FishSense
deployments 2, 3 and 4 excluded (timeline_dives.TEST_DEPLOYMENTS); REEF's pool calibration sessions stay in it.

v1 (production through 2026-09; frozen 2026-09-25 dump, data/db_extracts/dive_calibration_status.psv,
sql/extract_dive_calibration_status.sql): a dive has a calibration (laserextrinsics), a recorded refusal
(dive.calibration_refused_reason, grouped by its gate: range span < 0.6 m, laser baseline outside 7.8-14.5 cm,
checkerboard with < 2 usable laser points), or neither. Populations: dives with live human slate labels (slate
calibration) and dives with a checkerboard target.

fishsense-services (data/fishsense_services/slate_pose_calibrations.csv, read-only export 2026-10-31):
  slate-pose   each mission's current slate-pose-6 fit per laser aim, accepted or refused by reason
  moves        missions with a row for a second laser aim (aim 1): the missions whose recorded beam move got a
               fit attempt; the detector is fishsense-services beam_moves.py
  borrowed     a dive whose own slate-pose fit is not accepted for an aim but takes an accepted borrowed fit
Writes analysis/codesign/results/calibration_trust.csv.
Run: uv run python analysis/codesign/calibration_trust.py
"""
from __future__ import annotations

import sys

import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import physical_dives as PD  # noqa: E402
import timeline_dives as T  # noqa: E402


def gate(reason):
    r = str(reason)
    return ("range span < 0.6 m" if r.startswith("laser observations span") else
            "laser baseline outside 7.8-14.5 cm" if r.startswith("fitted laser baseline") else
            "checkerboard: < 2 usable laser points" if r.startswith("insufficient checkerboard") else r)


def main():
    K = PD.load().set_index("dive_id")
    canon = K.index[K.kind == "canonical"]
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv")
    test = set(M.dive_id[M.deployment_number.isin(T.TEST_DEPLOYMENTS)])
    field = [d for d in canon if d not in test]
    rows = []

    V = pd.read_csv(REPO / "data/db_extracts/dive_calibration_status.psv", sep="|", header=None,
                    names=["dive_id", "has_cal", "reason", "slate_labels", "target"]).set_index("dive_id")
    V["state"] = [("calibrated" if c == "t" else "refused: " + gate(r) if pd.notna(r) else "neither")
                  for c, r in zip(V.has_cal, V.reason)]
    # a physical dive's state from any of its records (calibrated beats refused beats neither)
    rank = {"calibrated": 0}
    V["phys"] = V.index.map(K.physical_dive)
    for pop, sel in (("v1 slate (physical dives with live human slate labels)", V.slate_labels > 0),
                     ("v1 checkerboard (physical dives with a checkerboard target)", V.target.notna())):
        g = V[sel].copy()
        g["r"] = g.state.map(lambda s: rank.get(s, 1 if s.startswith("refused") else 2))
        st = g.sort_values("r").groupby("phys").state.first()
        for f, name in ((st.index, "all"), ([d for d in st.index if d not in test], "field")):
            c = st.loc[list(f)].value_counts()
            for s, n in c.items():
                rows.append(dict(item=pop, population=name, outcome=s, physical_dives=int(n), of=len(f)))

    C = pd.read_csv(REPO / "data/fishsense_services/slate_pose_calibrations.csv")
    C["phys"] = C.mission_v1_id.map(K.physical_dive)
    C = C[C.mission_v1_id.isin(canon)]                     # a physical dive's own mission row
    sp = C[C.method == "slate_pose"]
    for aim in (0, 1):
        s = sp[sp.aim == aim]
        for name, f in (("all", s), ("field", s[~s.mission_v1_id.isin(test)])):
            for o, n in f.outcome.value_counts().items():
                rows.append(dict(item=f"slate-pose-6, aim {aim}", population=name, outcome=o, physical_dives=int(n), of=len(f)))

    moved = C[C.aim == 1].mission_v1_id.unique()
    for name, f in (("all", moved), ("field", [d for d in moved if d not in test])):
        rows.append(dict(item="beam move with a second-aim fit attempt", population=name, outcome="moved",
                         physical_dives=len(f), of=len(canon) if name == "all" else len(field)))
        acc = C[C.mission_v1_id.isin(f) & (C.aim == 1) & (C.outcome == "accepted")].mission_v1_id.nunique()
        rows.append(dict(item="beam move with a second-aim fit attempt", population=name, outcome="second aim calibrated (own or borrowed)",
                         physical_dives=acc, of=len(f)))

    own = C[(C.method == "slate_pose") & (C.outcome == "accepted")].set_index(["mission_v1_id", "aim"]).index
    b = C[(C.method == "borrowed") & (C.outcome == "accepted")]
    b = b[[(m, a) not in own for m, a in zip(b.mission_v1_id, b.aim)]]
    for name, f in (("all", b), ("field", b[~b.mission_v1_id.isin(test)])):
        for aim in (0, 1):
            rows.append(dict(item="borrowed calibration in use", population=name, outcome=f"aim {aim}",
                             physical_dives=int(f[f.aim == aim].mission_v1_id.nunique()),
                             of=len(canon) if name == "all" else len(field)))
        rows.append(dict(item="borrowed calibration in use", population=name, outcome="any aim",
                         physical_dives=int(f.mission_v1_id.nunique()), of=len(canon) if name == "all" else len(field)))
        lenders = f.borrowed_from_mission.value_counts()
        rows.append(dict(item="borrowed calibration in use", population=name, outcome="lenders",
                         physical_dives=len(lenders), of=int(lenders.max()) if len(lenders) else 0))
    R = pd.DataFrame(rows)
    R.to_csv(REPO / "analysis/codesign/results/calibration_trust.csv", index=False)
    pd.set_option("display.width", 220, "display.max_colwidth", 70)
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
