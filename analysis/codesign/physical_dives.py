"""Which dive records are the same physical dive: one row per record (all 525), with its kind and the record that
stands for its physical dive.

The same camera card was imported several times, from different data dumps, and each import folder became its own
dive record; images are deduplicated by checksum, and only the first registration of a checksum is canonical
(`uq_image_canonical_checksum`). So a record can repeat images counted elsewhere:

kind       canonical  the record holds canonical images and is not wholly inside another record.
           duplicate  the record holds no canonical image: every image is a byte-identical copy of a canonical image
                      in another record (a re-import of the same card; dive 333 copies records from two cameras).
                      It stands for the source record holding most of its images.
           fragment   the record holds canonical images, but every one of its distinct checksums is also held by one
                      other record that holds canonical images, comes from the same camera and whose images come from
                      one camera: a burst or the first stretch of a session that another import kept in one folder.
                      It stands for that record (the largest, if several). Dives 329 and 330 lie inside 344, which
                      merges two cameras' dates, and stay canonical.
partial    True for a canonical record sharing some but not all of its images with another canonical record:
           dives 18 and 32 (7 of 32's 13 images are in 18), and 344 (it holds copies of 329's and 330's). Each is
           kept as its own dive.
physical_dive  the canonical record the row stands for (itself for a canonical record).

Each physical dive counted once = the canonical rows. The author's decision (2026-10-27): drop duplicates and
fragments. Of all 525 records: 299 physical dives, 208 duplicates, 18 fragments (one, 508 inside 510, in a test
deployment). Field dives exclude FishSense deployments 2, 3, 4 (timeline_dives.TEST_DEPLOYMENTS): 481 records,
257 physical dives, 207 duplicates, 17 fragments.

Inputs: data/db_extracts/dive_checksums.psv (sql/extract_dive_checksums.sql), data/db_extracts/dive_overlap.psv
(sql/extract_dive_overlap.sql). Writes analysis/codesign/results/physical_dives.csv.
Run: uv run python analysis/codesign/physical_dives.py
"""
from __future__ import annotations

import pandas as pd

from fishsense_cscw.paths import REPO

DB = REPO / "data/db_extracts"


def load():
    C = pd.read_csv(DB / "dive_checksums.psv", sep="|", header=None,
                    names="dive_id images checksums canonical first last image_cameras camera_id".split()).set_index("dive_id")
    O = pd.read_csv(DB / "dive_overlap.psv", sep="|", header=None, names=["a", "b", "shared"])
    O = O.assign(inside=O.shared == O.a.map(C.checksums))

    kind = pd.Series("canonical", index=C.index)
    kind[C.canonical == 0] = "duplicate"
    holders = C.index[C.canonical > 0]
    single = C.image_cameras == 1
    F = O[O.a.isin(holders) & O.b.isin(holders) & O.inside
          & (O.a.map(C.camera_id) == O.b.map(C.camera_id)) & O.b.map(single)]
    F = F.assign(size=F.b.map(C.checksums)).sort_values(["a", "size"], ascending=[True, False]).drop_duplicates("a")
    kind[F.a] = "fragment"

    # a duplicate stands for the source holding most of its images; a fragment for its largest container
    dup = O[O.a.isin(C.index[kind == "duplicate"]) & O.b.isin(holders)].sort_values(["a", "shared"], ascending=[True, False]).drop_duplicates("a")
    rep = pd.Series(C.index, index=C.index)
    rep[dup.a] = dup.b.to_numpy()
    rep[F.a] = F.b.to_numpy()
    for _ in range(3):                                    # resolve chains (a duplicate of a fragment, a fragment in a fragment)
        rep = rep.map(lambda r: rep[r] if kind[r] != "canonical" else r)
    assert (kind[rep] == "canonical").all()

    canon = C.index[kind == "canonical"]
    P = O[O.a.isin(canon) & O.b.isin(canon) & ~O.inside]
    out = pd.DataFrame({"kind": kind, "physical_dive": rep, "partial": C.index.isin(P.a)})
    out.index.name = "dive_id"
    assert (out.kind == "duplicate").sum() == 208 and (out.kind == "fragment").sum() == 18, out.kind.value_counts()
    return out.reset_index()


def main():
    X = load()
    X.to_csv(REPO / "analysis/codesign/results/physical_dives.csv", index=False)
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv")
    import timeline_dives as T  # noqa: E402  (same directory)
    X = X.merge(M[["dive_id", "deployment_number"]], on="dive_id", how="left")
    field = ~X.deployment_number.isin(T.TEST_DEPLOYMENTS)
    print("all records:", X.kind.value_counts().to_dict(), "physical dives:", int((X.kind == "canonical").sum()))
    print("field records:", X[field].kind.value_counts().to_dict(), "physical dives:", int((X[field].kind == "canonical").sum()))
    print("fragments:", X[X.kind == "fragment"][["dive_id", "physical_dive"]].values.tolist())
    print("partial:", X[X.partial].dive_id.tolist())


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(REPO / "analysis/codesign"))
    main()
