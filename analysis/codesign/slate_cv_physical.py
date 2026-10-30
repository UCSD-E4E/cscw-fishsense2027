"""The slate-presence classifier's cross-validation with folds grouped by physical dive, beside the stored run
(data/slate_detector/oof_cv_q1.csv, folds grouped by dive record).

Two records of one physical dive could fall in different folds of the stored run: dives 18 and 26 (50 frames;
physical_dives.py). The rerun changes only the grouping: the same 6,828-frame manifest, labels and config
(efficientnet_b0, 12 epochs, 1024 px, batch 4, seed 0, 5 folds), with each frame's dive_id replaced by its
physical dive. The GPU-free check reads torch instead of nvidia-smi, which segfaults on this machine; the
detector repo is not edited.

Train (in ../2026-10-03_slate_detector, about 2.6 h on the 6 GB laptop GPU; writes runs/<out>/oof_predictions.csv):
  cd ../2026-10-03_slate_detector && env -u VIRTUAL_ENV LD_LIBRARY_PATH=/run/opengl-driver/lib \
    uv run --extra train python ../cscw-fishsense2027/analysis/codesign/slate_cv_physical.py train data/frames runs/cv-q1-physical
Copy (paths dropped, as for oof_cv_q1.csv):
  uv run python analysis/codesign/slate_cv_physical.py copy ../2026-10-03_slate_detector/runs/cv-q1-physical/oof_predictions.csv
Summarize (writes analysis/codesign/results/slate_cv_physical.csv):
  uv run python analysis/codesign/slate_cv_physical.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data/slate_detector"
PHYS = REPO / "analysis/codesign/results/physical_dives.csv"


def train(cache: Path, out: Path) -> None:
    import dataclasses  # pylint: disable=import-outside-toplevel

    import torch  # pylint: disable=import-outside-toplevel
    from slate_detector import train as TR  # pylint: disable=import-outside-toplevel
    from slate_detector.dataset import read_manifest  # pylint: disable=import-outside-toplevel

    def require_free_gpu(min_free_mib: int = TR.MIN_FREE_GPU_MIB) -> None:
        free, _ = torch.cuda.mem_get_info()
        if free / 2**20 < min_free_mib:
            raise RuntimeError(f"GPU has {free / 2**20:.0f} MiB free, need {min_free_mib}")

    TR.require_free_gpu = require_free_gpu
    phys = pd.read_csv(PHYS).set_index("dive_id").physical_dive
    frames = [dataclasses.replace(f, dive_id=int(phys[f.dive_id])) for f in read_manifest(Path("data/manifest.csv"))]
    TR.cross_validate(frames, cache, out, TR.TrainConfig(), folds=5)


def copy(oof: Path) -> None:
    """Keep the stored run's columns; dive_id goes back to the record, cutting_board and labels from oof_cv_q1.csv."""
    old = pd.read_csv(DATA / "oof_cv_q1.csv").set_index("image_id")
    new = pd.read_csv(oof).set_index("image_id").reindex(old.index)
    assert new.fold.notna().all() and (new.label == old.label).all()   # same frames, same labels (dive 526 relabel in both)
    out = old[["dive_id"]].assign(fold=new.fold, label=old.label, p_slate=new.p_slate, cutting_board=old.cutting_board)
    out.reset_index().to_csv(DATA / "oof_cv_q1_physical.csv", index=False)


def score(o: pd.DataFrame, phys: pd.Series) -> dict:
    o = o[o.cutting_board == 0]
    hit, pos = o.p_slate >= 0.5, o.label == 1
    tp, fp, fn = (hit & pos).sum(), (hit & ~pos).sum(), (~hit & pos).sum()
    found = o[pos].assign(hit=hit[pos]).groupby(o.dive_id[pos].map(phys)).hit.any()
    return {"frames": len(o), "slate": int(pos.sum()), "precision": round(tp / (tp + fp), 4), "recall": round(tp / (tp + fn), 4),
            "false_positives": int(fp), "false_negatives": int(fn), "physical_dives_found": int(found.sum()),
            "physical_dives_with_slate": len(found), "missed_dives": " ".join(map(str, found.index[~found])),
            "folds_splitting_a_physical_dive": int((o.groupby(o.dive_id.map(phys)).fold.nunique() > 1).sum())}


def main() -> None:
    phys = pd.read_csv(PHYS).set_index("dive_id").physical_dive
    rows = {g: score(pd.read_csv(DATA / f), phys) for g, f in
            (("record", "oof_cv_q1.csv"), ("physical_dive", "oof_cv_q1_physical.csv"))}
    R = pd.DataFrame(rows).T.rename_axis("folds_grouped_by")
    R.to_csv(REPO / "analysis/codesign/results/slate_cv_physical.csv")
    print(R.T.to_string())


if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        train(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1:2] == ["copy"]:
        copy(Path(sys.argv[2]))
    else:
        main()
