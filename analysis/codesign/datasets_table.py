"""Counts for the SenSys datasets table, each from the committed file the paper's numbers come from.

Dives are physical dives (physical_dives.py). Capture dates: first and last capture time of the dataset's records'
canonical images (data/db_extracts/dive_effort.psv, camera clock). Field = not a FishSense test deployment (2, 3, 4;
timeline_dives.TEST_DEPLOYMENTS), as calibration_trust.py.

  archive          physical_dives.csv; canonical images (data/db_extracts/image_counts.psv)
  pool ladder      stage_comparison_frames.csv set "pool": fish-model frames on the stage ladder's 10 dives; fish =
                   one model in one dive
  field 7          stage_comparison_frames.csv set "field", the 7 dives, frames people measured and rejected; fish =
                   Label Studio cluster (field_disagreement_frames.csv)
  slate pose       slatepose_vs_human.csv (17 dives); live human laser dots and slate-pose fit frames
  pre-fills        labelling.seed_moves(): detector-seeded laser annotations, dives as intro_numbers.py item 2d
  detector         label_setup.py item 4: the training corpus rebuilt as it stood on 2026-05-04 (completed, positive,
                   not superseded labels made before then), after the detector's line filter
Writes analysis/codesign/results/datasets_table.csv.
Run: uv run python analysis/codesign/datasets_table.py
"""
from __future__ import annotations

import sys

import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import labelling  # noqa: E402
import label_setup  # noqa: E402
import physical_dives as PD  # noqa: E402
import timeline_dives as T  # noqa: E402

RES = REPO / "analysis/codesign/results"


def main():
    K = PD.load().set_index("dive_id"); phys = K.physical_dive
    E = pd.read_csv(REPO / "data/db_extracts/dive_effort.psv", sep="|", header=None, usecols=[0, 2, 3, 4], names=["dive_id", "images", "first", "last"])
    E["first"], E["last"] = pd.to_datetime(E["first"], utc=True), pd.to_datetime(E["last"], utc=True)
    E["phys"] = E.dive_id.map(phys)

    def span(records=None, physical=None):
        x = E[E.dive_id.isin(records)] if records is not None else E[E.phys.isin(physical)]
        return f"{x['first'].min():%Y-%m-%d} .. {x['last'].max():%Y-%m-%d}"

    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv")
    test = set(M.dive_id[M.deployment_number.isin(T.TEST_DEPLOYMENTS)])
    canon = K.index[K.kind == "canonical"]
    imgs = pd.read_csv(REPO / "data/db_extracts/image_counts.psv", sep="|", header=None, names=["m", "n"]).set_index("m").n
    rows = [dict(dataset="archive", physical_dives=K.physical_dive.nunique(), frames=int(imgs["canonical images"]),
                 units=f"{len(K)} records; {sum(d not in test for d in canon)} field physical dives", capture=span(records=K.index))]

    F = pd.read_csv(RES / "stage_comparison_frames.csv", low_memory=False)
    P = F[F.set == "pool"]
    rows.append(dict(dataset="pool stage ladder (taped fish models)", physical_dives=P.dive.map(phys).nunique(), frames=len(P),
                     units=f"{P.groupby(['dive', 'target']).ngroups} fish (model x dive), {P.target.nunique()} models", capture=span(records=P.dive.unique())))
    R = F[(F.set == "field") & F.dive.isin([279, 341, 347, 349, 383, 465, 471])]
    meas = R.measured.astype(str).eq("True")
    fd = pd.read_csv(RES / "field_disagreement_frames.csv"); fd = fd[fd.dive_id.isin(R.dive.unique())]
    rows.append(dict(dataset="reef dives with human labels (field comparison)", physical_dives=R.dive.map(phys).nunique(), frames=int(meas.sum()),
                     units=f"{int((~meas).sum())} human-rejected frames; {fd.fish.nunique()} fish (Label Studio clusters)", capture=span(records=R.dive.unique())))
    SP = pd.read_csv(RES / "slatepose_vs_human.csv")
    rows.append(dict(dataset="slate-pose vs human calibration", physical_dives=SP.dive.map(phys).nunique(), frames=int(SP.slate_pose_frames.sum()),
                     units=f"{int(SP.dots.sum())} live human laser dots scored; frames = slate frames the slate-pose fits used", capture=span(records=SP.dive.unique())))
    sm = labelling.seed_moves(); sm = sm[(sm.kind == "laser") & (sm.seed == "model")]
    dive = pd.read_csv(REPO / "data/db_extracts/annotations.psv", sep="|", header=None, usecols=[2, 3], names=["image_id", "dive_id"]).drop_duplicates("image_id")
    sm = sm.merge(dive, on="image_id", how="left").dropna(subset=["dive_id"])
    rows.append(dict(dataset="pre-fill acceptance (detector seeds)", physical_dives=sm.dive_id.astype(int).map(phys).nunique(), frames=sm.image_id.nunique(),
                     units=f"{sm.ann_id.nunique()} annotations; labeled {sm.created_at.min():%Y-%m-%d} .. {sm.created_at.max():%Y-%m-%d}",
                     capture=span(physical=sm.dive_id.astype(int).map(phys).unique())))
    _, C = label_setup.item4(label_setup.load())
    C = C[~C.outlier]
    rows.append(dict(dataset="laser detector training corpus (2026-05-04, rebuilt)", physical_dives=C.dive_id.map(phys).nunique(), frames=C.image_id.nunique() if "image_id" in C else len(C),
                     units=f"{len(C)} positive labels; labeled {C.t.min():%Y-%m-%d} .. {C.t.max():%Y-%m-%d}; train = 80% of record dives (seed 0)",
                     capture=span(records=C.dive_id.unique())))
    D = pd.DataFrame(rows); D.to_csv(RES / "datasets_table.csv", index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print(D.to_string(index=False))


if __name__ == "__main__":
    main()
