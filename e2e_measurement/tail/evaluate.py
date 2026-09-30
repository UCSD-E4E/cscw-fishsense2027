"""Tail study, scoring: production tail vs caudal-fork tail, on the pool (tape) and on reef fish.

Pool (fish models, tape truth): automatic dot -> SAM mask at that dot -> head/tail rule ->
  length with the stored slate calibration and with the label-free one. Per-fish production
  estimator (p90 over a dive x model), as in ../score.py.
Reef (real fish, no tape):
  keypoints  mask seeded by the HUMAN dot, so only the head/tail stage differs from the human:
             head and tail distance to the human clicks (as a fraction of the human length) and
             the pixel-length ratio auto/human.
  lengths    on the 8 reef dives with a stored calibration: fully automatic length (auto dot,
             auto head/tail) vs the manual length (human dot + human head/tail), same calibration.
  dots       automatic dot vs the human click, by laser colour.

Run from this repo:  uv run python evaluate.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import score as S  # noqa: E402  (depth, length, calibrations, KNOWN, PAIR, p90)

RULES = ["prod", "fork03", "fork02", "fork05"]


def load():
    F = pd.read_csv(HERE / "frames.csv")
    K = pd.read_csv(HERE / "keypoints.csv")
    dots = {}
    for name in (HERE.parent / "dots.jsonl", HERE / "reef_dots.jsonl"):
        if name.exists():
            for l in name.open():
                r = json.loads(l)
                if "dot" in r and r["dot"]["x"] is not None:
                    dots[r["image_id"]] = (r["dot"]["x"], r["dot"]["y"])
    return F, K, dots


def tail_of(k, rule):
    return (k["prod_tail_x"], k["prod_tail_y"]) if rule == "prod" else (k[f"{rule}_tail_x"], k[f"{rule}_tail_y"])


def main():
    F, K, dots = load(); stored, labelfree, intr = S.calibrations()
    Kx = K.set_index(["image_id", "seed"])
    pd.set_option("display.width", 220)

    # ---- pool: tape truth
    pool = F[F.set == "pool"].copy(); pool["model"] = pool.content.str.split(", ").str[-1]; pool["L_true"] = pool.model.map(S.KNOWN)
    rows = []
    for r in pool.itertuples():
        if (r.image_id, "auto") not in Kx.index or r.image_id not in dots:
            continue
        k = Kx.loc[(r.image_id, "auto")]
        if pd.isna(k.get("head_x")):
            continue
        Kc = intr[int(r.camera_id)]; x, y = dots[r.image_id]
        for cal_name, cal in (("stored", stored.get(S.PAIR[int(r.dive_id)])), ("labelfree", labelfree.get(S.PAIR[int(r.dive_id)]))):
            if cal is None:
                continue
            Z = S.depth(Kc, cal[0], cal[1], x, y)
            for rule in RULES:
                tx, ty = tail_of(k, rule)
                L = S.length(Kc, Z, k.head_x, k.head_y, tx, ty)
                rows.append(dict(image_id=r.image_id, dive=r.dive_id, model=r.model, cal=cal_name, rule=rule, L=L, err=L / r.L_true - 1))
    P = pd.DataFrame(rows)
    if len(P):
        n_pool = len(pool)
        print(f"POOL (tape): {len(pool)} frames staged; measured {P.image_id.nunique()} ({P.image_id.nunique() / n_pool:.0%})")
        out = []
        for (cal, rule), g in P.groupby(["cal", "rule"]):
            est = pd.Series({k: S.p90(t.L) / (t.L / (1 + t.err)).iloc[0] - 1 for k, t in g.groupby(["dive", "model"])})   # L_true = L / (1 + err)
            by_model = {m: pd.Series({k: v for k, v in est.items() if k[1] == m}).abs().mean() for m in sorted(g.model.unique())}
            out.append(dict(cal=cal, rule=rule, frame_median=g.err.median(), fish_p90_mae=est.abs().mean(), fish_n=len(est),
                            **{f"mae_{m}": v for m, v in by_model.items()}))
        print(pd.DataFrame(out).round(3).to_string(index=False))

    # ---- reef: keypoints vs human clicks (human-seeded masks)
    reef = F[F.set == "reef"]
    rows = []
    for r in reef.itertuples():
        if (r.image_id, "human") not in Kx.index:
            continue
        k = Kx.loc[(r.image_id, "human")]
        if pd.isna(k.get("head_x")):
            rows.append(dict(image_id=r.image_id, status=k.mask_status)); continue
        hh = np.array([r.head_x, r.head_y]); ht = np.array([r.tail_x, r.tail_y]); Lh = np.linalg.norm(ht - hh)
        for rule in RULES:
            t = np.array(tail_of(k, rule), float); h = np.array([k.head_x, k.head_y])
            # the rule's head/tail may be swapped relative to the human; score the better assignment
            direct = np.linalg.norm(h - hh) + np.linalg.norm(t - ht); swapped = np.linalg.norm(h - ht) + np.linalg.norm(t - hh)
            if swapped < direct:
                h, t = t, h
            rows.append(dict(image_id=r.image_id, dive=r.dive_id, green=str(r.laser_label).startswith("Green"), status="ok", rule=rule,
                             swapped=swapped < direct, head_err=np.linalg.norm(h - hh) / Lh, tail_err=np.linalg.norm(t - ht) / Lh,
                             ratio=np.linalg.norm(t - h) / Lh))
    R = pd.DataFrame(rows)
    if len(R):
        n = R.image_id.nunique(); okR = R[R.status == "ok"]
        print(f"\nREEF keypoints (human-seeded masks): {n} frames; mask ok {okR.image_id.nunique() / n:.0%}")
        print(okR.groupby("rule").agg(frames=("ratio", "size"), head_err_med=("head_err", "median"), tail_err_med=("tail_err", "median"),
                                      ratio_med=("ratio", "median"), ratio_mae=("ratio", lambda s: (s - 1).abs().mean()),
                                      within5=("ratio", lambda s: ((s - 1).abs() <= .05).mean()), within10=("ratio", lambda s: ((s - 1).abs() <= .10).mean()),
                                      swapped=("swapped", "mean")).round(3).to_string())

    # ---- reef: automatic vs manual length on calibrated dives
    rows = []
    for r in reef.itertuples():
        cal = stored.get(int(r.dive_id))
        if cal is None or r.image_id not in dots or (r.image_id, "auto") not in Kx.index:
            continue
        k = Kx.loc[(r.image_id, "auto")]
        Kc = intr[int(r.camera_id)]
        Zm = S.depth(Kc, cal[0], cal[1], r.laser_x, r.laser_y)
        Lm = S.length(Kc, Zm, r.head_x, r.head_y, r.tail_x, r.tail_y)
        if pd.isna(k.get("head_x")):
            rows.append(dict(image_id=r.image_id, dive=r.dive_id, rule="(no mask)", Lm=Lm)); continue
        Za = S.depth(Kc, cal[0], cal[1], *dots[r.image_id])
        for rule in RULES:
            La = S.length(Kc, Za, k.head_x, k.head_y, *tail_of(k, rule))
            rows.append(dict(image_id=r.image_id, dive=r.dive_id, green=str(r.laser_label).startswith("Green"), rule=rule, Lm=Lm, La=La, rel=La / Lm - 1))
    M = pd.DataFrame(rows)
    if len(M) and "rel" in M:
        n = M.image_id.nunique(); okM = M.dropna(subset=["rel"])
        print(f"\nREEF lengths, calibrated dives: {n} frames; automatic length produced for {okM.image_id.nunique() / n:.0%}")
        print(okM.groupby("rule").agg(frames=("rel", "size"), median=("rel", "median"), mae=("rel", lambda s: s.abs().mean()),
                                      within5=("rel", lambda s: (s.abs() <= .05).mean()), within10=("rel", lambda s: (s.abs() <= .10).mean())).round(3).to_string())

    # ---- dots
    d = [dict(image_id=r.image_id, green=str(r.laser_label).startswith("Green"), err=np.hypot(dots[r.image_id][0] - r.laser_x, dots[r.image_id][1] - r.laser_y))
         for r in reef.itertuples() if r.image_id in dots]
    D = pd.DataFrame(d)
    if len(D):
        print("\nREEF automatic dot vs human click (px):")
        print(D.groupby("green").err.describe(percentiles=[.5, .9]).round(1).rename(index={True: "green", False: "red"}).to_string())
        print(f"   frames staged without an automatic dot: {len(reef) - len(D)} of {len(reef)}")


if __name__ == "__main__":
    main()
