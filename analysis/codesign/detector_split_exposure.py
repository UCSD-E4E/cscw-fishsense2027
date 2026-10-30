"""How much of the deployed RAW laser detector's test set could have a record of the same physical dive in training.

The detector (UCSD-E4E/2026-05-02_laser_detector) splits by dive record 80/10/10 (preprocessing/splits.py
make_dive_splits, seed 0, stratified by a wavelength clustered from pixels), over every laser label's image
(ingest.py), without filtering to canonical images. Its split table (data/phase0/dive_splits.parquet) is not
committed and is not on this machine, and the wavelength step needs the pixels, so the actual split cannot be
rebuilt. Instead:

1. byte-identical copies: whether any positive label's image is labeled positive in more than one record;
2. near-duplicates: positives in physical dives (physical_dives.py) whose positives span several records;
3. exposure under 2,000 random 80/10/10 record splits (not stratified by wavelength): the share of test
   positives with a byte-identical copy, or a record of the same physical dive, in training.

Input: data/db_extracts/detector_label_frames.psv (sql/extract_detector_label_frames.sql).
Writes analysis/codesign/results/detector_split_exposure.csv.
Run: uv run python analysis/codesign/detector_split_exposure.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import physical_dives as PD  # noqa: E402

DRAWS = 2000


def main():
    F = pd.read_csv(REPO / "data/db_extracts/detector_label_frames.psv", sep="|", header=None,
                    names="label image dive checksum canonical positive completed".split())
    for c in ("canonical", "positive", "completed"):
        F[c] = F[c].eq("t")
    K = PD.load().set_index("dive_id")
    F["phys"] = F.dive.map(K.physical_dive)
    P = F[F.positive]
    copies = P.groupby("checksum").dive.nunique().gt(1)
    span = P.groupby("phys").dive.nunique()
    near = P[P.phys.isin(span.index[span > 1])]
    print(f"{len(F)} labels, {len(P)} positive, {F.dive.nunique()} records = {F.phys.nunique()} physical dives")
    print(f"positives on non-canonical images: {(~P.canonical).sum()}; checksums positive in >1 record: {copies.sum()}")
    print(f"physical dives with positives in >1 record: {len(near.phys.unique())}, {len(near)} positives")
    print(near.groupby(["phys", "dive"]).size().rename("positives").to_frame().join(K.kind, on="dive").to_string())

    dives = np.array(sorted(F.dive.unique()))
    rng = np.random.default_rng(1)
    rows = []
    for _ in range(DRAWS):
        d = rng.permutation(dives)
        n_tr, n_va = round(0.8 * len(d)), round(0.1 * len(d))
        split = pd.Series(["train"] * n_tr + ["val"] * n_va + ["test"] * (len(d) - n_tr - n_va), index=d)
        s = P.dive.map(split)
        T, tr = P[s == "test"], P[s == "train"]
        rows.append((len(T), T.checksum.isin(tr.checksum).sum(), T.phys.isin(tr.phys).sum()))
    R = pd.DataFrame(rows, columns=["test_positives", "byte_identical_in_train", "same_physical_dive_in_train"])
    R["share_same_physical_dive"] = 100 * R.same_physical_dive_in_train / R.test_positives
    Q = R.quantile([0.5, 0.025, 0.975]).round(1)
    Q.index = ["median", "p2.5", "p97.5"]
    Q.to_csv(REPO / "analysis/codesign/results/detector_split_exposure.csv")
    print(Q.to_string())


if __name__ == "__main__":
    main()
