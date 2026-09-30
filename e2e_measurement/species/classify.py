"""Species stage, pass 2: BioCLIP 2.5 on the crops, scored against the human species labels.

Uses coral-gardeners-fish-detector's classifier unchanged (zero-shot open_clip, 4 prompt
templates per species, softmax over the closed list) with its `little_cayman` list -- the 13
REEF species of interest, which is also FishSense's labelling list. Offline from the local
weights: HF_HUB_OFFLINE=1, so the token in that repo's cache is never used.

Variants per frame: ht (human head/tail box), sam (SAM 3.1 mask box), masked (mask, background
zeroed), best (coral-gardeners' rule: the more confident of sam and masked).
"Other (Identifiable but Nontarget)" frames test open-set rejection: with a closed list every
crop gets a species, so we report how well top-1 probability separates targets from others.

Run from coral-gardeners-fish-detector's venv:
  HF_HUB_OFFLINE=1 HF_HOME=<repo>/models/hf_cache LD_LIBRARY_PATH=/run/opengl-driver/lib \\
      <repo>/.venv/bin/python classify.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
CG = HERE.parents[2] / "coral-gardeners-fish-detector"
sys.path.insert(0, str(CG / "src"))


def classify():
    from coral_fish_pipeline.classification.bioclip_classifier import BioCLIPClassifier
    species = yaml.safe_load((CG / "resources/top25.yaml").read_text())
    species = next(v for k, v in _regions(species) if k == "little_cayman")["names"]
    clf = BioCLIPClassifier(species=species, region="little_cayman", unknown_threshold=0.0, uncertain_margin=0.0,
                            cache_dir=HERE / "bioclip_cache", classify_masked_crops=False)
    clf.load(); print("model", clf.model_id, flush=True)
    out = HERE / "bioclip.jsonl"
    done = {json.loads(l)["key"] for l in out.open()} if out.exists() else set()
    with out.open("a") as fh:
        for p in sorted((HERE / "crops").glob("*.jpg")):
            if p.stem in done:
                continue
            pred = clf._predict_image(p)
            iid, variant = p.stem.split("_", 1)
            fh.write(json.dumps(dict(key=p.stem, image_id=int(iid), variant=variant, species=pred["species"],
                                     p1=pred["top1_probability"], margin=pred["margin"], top5=pred["top5"])) + "\n")
    print("done", flush=True)


def _regions(y):
    """top25.yaml nests region blocks; yield (name, block) wherever a block has `names`."""
    stack = [(None, y)]
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            if "names" in v:
                yield k, v
            stack.extend(v.items())


def score():
    F = pd.read_csv(HERE / "frames.psv", sep="|")
    F["truth"] = F.content.str.extract(r"\(([^)]+)\)")[0]
    F.loc[F.content.str.contains("Other"), "truth"] = "OTHER"
    P = pd.DataFrame([json.loads(l) for l in (HERE / "bioclip.jsonl").open()])
    W = P.pivot_table(index="image_id", columns="variant", values=["species", "p1"], aggfunc="first")
    W.columns = [f"{a}_{b}" for a, b in W.columns]
    if {"species_sam", "species_masked"} <= set(W.columns):
        use_m = W.p1_masked > W.p1_sam
        W["species_best"] = np.where(use_m, W.species_masked, W.species_sam); W["p1_best"] = np.where(use_m, W.p1_masked, W.p1_sam)
    D = F.set_index("image_id").join(W, how="inner")
    tgt = D[D.truth != "OTHER"]
    pd.set_option("display.width", 200)
    print(f"{len(D)} frames with crops ({len(tgt)} target-species, {(D.truth == 'OTHER').sum()} other)")
    for v in ("ht", "sam", "masked", "best"):
        col = f"species_{v}"
        if col not in D:
            continue
        t = tgt.dropna(subset=[col])
        hit = t[col] == t.truth
        acc = hit.mean()
        per_sp = hit.groupby(t.truth).mean()
        # per dive x species: majority vote over frames (a crude per-fish estimate)
        vote = t.groupby(["dive_id", "truth"])[col].agg(lambda s: s.mode().iloc[0])
        vote_acc = (vote.index.get_level_values("truth") == vote.values).mean()
        o = D[D.truth == "OTHER"][f"p1_{v}"].dropna(); g = t[f"p1_{v}"]
        auc = (g.to_numpy()[:, None] > o.to_numpy()[None, :]).mean() if len(o) and len(g) else np.nan
        print(f"\n== {v}: top-1 {acc:.1%} on {len(t)} frames; balanced {per_sp.mean():.1%}; dive-level vote {vote_acc:.1%} ({len(vote)}); "
              f"target-vs-other AUC from top-1 prob {auc:.2f}")
        print("   per species:", {k: f"{val:.0%} (n={int((t.truth == k).sum())})" for k, val in per_sp.items()})
    col = "species_best" if "species_best" in D else "species_ht"
    print(f"\nconfusion ({col}):"); print(pd.crosstab(tgt.truth, tgt[col]).to_string())


if __name__ == "__main__":
    classify() if sys.argv[1] == "classify" else score()
