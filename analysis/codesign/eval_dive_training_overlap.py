"""Are the evaluation dives in the models' training data? A lookup, per dive and per physical dive.

Dives: the stage ladder's 10 pool fish-model dives (score.py: 58, 59, 60, 61, 66, 76, 84, 87, 94, 114) and the 7 reef
evaluation dives (stage_comparison.FIELD: 279, 341, 347, 349, 383, 465, 471). Physical dives: physical_dives.py.

Laser detector (run3): its split table (data/phase0/dive_splits.parquet, 80/10/10 by record, seed 0, stratified by a
pixel wavelength) was never committed and is not on this machine (detector_split_exposure.py), so the split cannot be
read. Reported instead: the training corpus as it stood on 2026-05-04 (label_setup.py item 4: completed, positive,
not superseded laser labels made before then, after the detector's line filter; it undercounts slightly), as positives
on the dive's own record and on any record of its physical dive. Being in the corpus means 80% odds of being in train
for a record drawn at random, not that it was.

Keypoint model (SimCC, 2026-10-22_headtail_keypoints splits/dives.csv, by record): the dive record's own split, and
the training frames on any other record of its physical dive (splits/frames.csv).
Writes analysis/codesign/results/eval_dive_training_overlap.csv.
Run: uv run python analysis/codesign/eval_dive_training_overlap.py
"""
from __future__ import annotations

import sys

import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import label_setup  # noqa: E402
import physical_dives as PD  # noqa: E402

KPS = REPO.parent / "2026-10-22_headtail_keypoints/splits"
POOL = (58, 59, 60, 61, 66, 76, 84, 87, 94, 114)
REEF = (279, 341, 347, 349, 383, 465, 471)


def main():
    phys = PD.physical()
    _, C = label_setup.item4(label_setup.load())
    C = C[~C.outlier]                                  # per record (label_setup run without --physical)
    det_rec = C.groupby("dive_id").size()
    det_phys = C.assign(p=C.dive_id.map(phys)).groupby("p").size()
    S = pd.read_csv(KPS / "dives.csv").set_index("dive_id").split
    Fk = pd.read_csv(KPS / "frames.csv")
    Fk["p"] = Fk.dive_id.map(phys)
    rows = []
    for set_, dives in (("pool stage ladder", POOL), ("reef evaluation", REEF)):
        for d in dives:
            p = phys[d]
            others = [r for r in phys.index[phys == p] if r != d]
            kt = Fk[(Fk.p == p) & (Fk.dive_id != d) & (Fk.split == "train")]
            rows.append(dict(set=set_, dive=d, physical_dive=p, other_records=" ".join(map(str, others)),
                             detector_positives_record=int(det_rec.get(d, 0)), detector_positives_physical=int(det_phys.get(p, 0)),
                             keypoint_split=S.get(d, "not in split"),
                             keypoint_train_frames_other_records=len(kt),
                             keypoint_other_records_in_train=" ".join(map(str, sorted(kt.dive_id.unique())))))
    R = pd.DataFrame(rows)
    R.to_csv(REPO / "analysis/codesign/results/eval_dive_training_overlap.csv", index=False)
    pd.set_option("display.width", 220)
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
