"""Check the paper's labelling-time claims against the scripted data; writes only its own result file.

1  Per-task time per label: Label Studio `lead_time` (seconds the task was open until submission) for
   annotations not drawn from a pre-filled seed (no parent_prediction / parent_annotation), from the
   scripted extract data/db_extracts/lead_times_by_dive.psv (sql/extract_lead_times_by_dive.sql). Medians,
   with intervals resampling dives. No cap: idle tabs inflate the tail, so medians are used; the 300 s cap
   applies only to dive_time.py's recorded per-dive sums. Cross-checked against data/labeling/lead_times.csv,
   the file the paper's Figure fig8_labeling_time reads (no script in the repo produces it; added at d219182d),
   with an iid interval since it has no dive id. Sensitivity: after 2026-07-27 many laser labels with no
   parent link copy the detector's prediction exactly, so the laser median is also given for labels made
   before that date.
2-3,5  Read back from analysis/codesign/dive_time.py's stored results after re-running that script into a
   scratch directory and checking the per-dive table and summary reproduce exactly.
4  Each task's share of a field dive's estimated labelling time, and slate frames per dive (all field dives,
   imputed included, and only dives whose slate count is complete).
Intervals: 95%, resampling dives (2,000 draws).
--physical: each physical dive counted once (dive_time.py --physical; annotations regrouped by physical dive);
reads and writes the _physical files.

Writes analysis/codesign/results/labelling_time_claims.csv.
Run: uv run python analysis/codesign/labelling_time_claims.py [--physical]
"""
from __future__ import annotations

import sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import dive_time as DT  # noqa: E402

RES = REPO / "analysis/codesign/results"
N_BOOT = 2000
FIRST_PREFILL = pd.Timestamp("2026-07-27", tz="UTC")
rows = []


def add(claim, quantity, value, ci=(np.nan, np.nan), n="", definition="", source=""):
    rows.append(dict(claim=claim, quantity=quantity, value=value, ci_lo=ci[0], ci_hi=ci[1], n=n, definition=definition, source=source))


def cboot(d, stat, key="dive_id", seed=0):
    rng = np.random.default_rng(seed); g = [x for _, x in d.groupby(key)]
    return tuple(np.nanpercentile([stat(pd.concat([g[i] for i in rng.integers(0, len(g), len(g))])) for _ in range(N_BOOT)], [2.5, 97.5]))


def iboot(x, f=np.median, seed=0):
    x = np.asarray(x, float); rng = np.random.default_rng(seed)
    return tuple(np.percentile([f(x[rng.integers(0, len(x), len(x))]) for _ in range(N_BOOT)], [2.5, 97.5]))


def reproduce():
    with tempfile.TemporaryDirectory() as tmp:
        DT.OUT, DT.FIG = Path(tmp), Path(tmp)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            DT.main()
        ok = {}
        for f in (f"dive_time_dives{DT.SUFFIX}.csv", f"dive_time_summary{DT.SUFFIX}.csv"):
            a, b = pd.read_csv(Path(tmp) / f), pd.read_csv(RES / f)
            ok[f] = a.shape == b.shape and np.allclose(a.select_dtypes("number").fillna(-1), b.select_dtypes("number").fillna(-1), rtol=0, atol=1e-6)
    return ok


def main():
    A = pd.read_csv(REPO / "data/db_extracts/lead_times_by_dive.psv", sep="|", header=None, names=["kind", "dive_id", "image_id", "lead", "seeded", "created"])
    if DT.PHYSICAL:
        A["dive_id"] = A.dive_id.map(DT.PHYS)
    A["created"] = pd.to_datetime(A.created, utc=True, format="ISO8601"); U = A[A.seeded == "f"]
    C = pd.read_csv(REPO / "data/labeling/lead_times.csv"); C = C[C.seeded.astype(str).str.lower().isin(["f", "false"])]
    ref = {"laser": "laser_dot", "headtail": "head_tail", "species": "species", "slate": "slate_corners"}
    for k, name in DT.TASKS.items():
        s = U[U.kind == k]
        add(1, f"{name}: median s per label (scripted extract)", s.lead.median(), cboot(s, lambda z: z.lead.median()),
            f"{len(s):,} annotations, {s.dive_id.nunique()} dives; > 300 s {(s.lead > 300).mean():.1%}, > 1 h {(s.lead > 3600).mean():.2%}",
            "Label Studio lead_time, annotations without a pre-filled seed, no cap", "sql/extract_lead_times_by_dive.sql")
        c = C[C.label_type == ref[k]].lead_time_s
        add(1, f"{name}: median s per label (lead_times.csv, the figure's file)", c.median(), iboot(c), f"{len(c):,} annotations (iid interval)",
            "same field; unscripted extract", "data/labeling/lead_times.csv (d219182d)")
    s = U[(U.kind == "laser") & (U.created < FIRST_PREFILL)]
    add(1, "laser dot: median s, labels before 2026-07-27 only", s.lead.median(), cboot(s, lambda z: z.lead.median()), f"{len(s):,} annotations",
        "excludes the period when unlinked laser labels can be copies of the detector's prediction", "sql/extract_lead_times_by_dive.sql")
    add(1, "seeded annotations excluded", int((A.seeded == "t").sum()), n="annotations with parent_prediction or parent_annotation",
        definition="model pre-fills and earlier-human-label pre-fills both excluded")

    ok = reproduce()
    add("2-5", "dive_time.py reproduces its stored results", float(all(ok.values())), n=str(ok))
    S = pd.read_csv(RES / f"dive_time_summary{DT.SUFFIX}.csv").set_index(["set", "quantity"])
    D = pd.read_csv(RES / f"dive_time_dives{DT.SUFFIX}.csv")
    f = ("field (reef)",)
    def put(claim, q, label):
        r = S.loc[f + (q,)]
        add(claim, label, r.value, (r.ci_lo, r.ci_hi), f"{int(r.dives)} dives", q, "analysis/codesign/dive_time.py")
    put(2, "share of dives: estimated human > underwater", "share of field dives whose estimated labelling exceeds time underwater")
    put(3, "ratio estimated human / underwater", "median ratio estimated labelling / underwater")
    put(3, "underwater time, h (lower bound)", "median underwater time, h")
    put(3, "estimated human labelling, h", "median estimated labelling, h")
    reef = D[D.env == "reef"]
    add(3, "field dives before exclusions", len(reef)); add(3, "field dives excluded", int((reef.span_flag != "ok").sum()),
        n=str(reef[reef.span_flag != "ok"].span_flag.value_counts().to_dict()))
    put(5, "machine, h (dives with workflow runs)", "median machine time per field dive, h")

    # 4: task shares per field dive
    t = pd.read_csv(RES / f"dive_time_tasks{DT.SUFFIX}.csv", index_col=0).median_s.astype(float)
    F = D[(D.env == "reef") & (D.span_flag == "ok")].copy()
    tot = F.images * t["laser"] + F.fish_frames * (t["headtail"] + t["species"]) + F.slate_frames * t["slate"]
    F["laser"], F["snout/fork"], F["species"], F["slate"] = (F.images * t["laser"] / tot, F.fish_frames * t["headtail"] / tot,
                                                             F.fish_frames * t["species"] / tot, F.slate_frames * t["slate"] / tot)
    for c in ("laser", "snout/fork", "species", "slate"):
        add(4, f"{c}: median share of a field dive's estimated labelling time", F[c].median(), iboot(F[c]), f"{len(F)} dives")
    for name, X in (("all field dives (imputed included)", F), ("field dives with a complete slate count", F[F.slate_observed])):
        add(4, f"slate frames per dive, median, {name}", X.slate_frames.median(), iboot(X.slate_frames), f"{len(X)} dives")
    add(4, "images per field dive, median", F.images.median(), iboot(F.images), f"{len(F)} dives")
    add(4, "laser dot: share of field dives where it is the largest task", float((F.laser >= F[["snout/fork", "species", "slate"]].max(axis=1)).mean()),
        iboot((F.laser >= F[["snout/fork", "species", "slate"]].max(axis=1)).astype(float), np.mean))
    add(4, "snout/fork + species: median combined share", (F["snout/fork"] + F.species).median(), iboot(F["snout/fork"] + F.species))

    R = pd.DataFrame(rows); R.to_csv(RES / f"labelling_time_claims{DT.SUFFIX}.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
    print(R[["claim", "quantity", "value", "ci_lo", "ci_hi", "n"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
