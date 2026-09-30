"""Measurability gate: should the automatic pipeline measure this frame at all?

Label: did the human measure the frame (head/tail clicked) or skip it (label row without points).
Candidates: reef frames where some SAM 3.1 "fish" mask >= 0.1 contains the human dot (the widest
net; coverage_gpu.py). The candidate mask is the highest-scoring one containing the dot.
Features, all available automatically at run time (no human input):
  score            SAM confidence of the mask
  log_area         mask area
  elong            sqrt of the PCA eigenvalue ratio (long / short axis)
  silhouette       area / (PCA length)^2
  solidity         area / convex-hull area
  edge             fraction of the window border the mask touches
  dot_axial        where the dot sits along the body (0 = centre, 1 = an end)
  dot_lateral      dot distance from the body axis, / length
  n_masks          other masks (>= 0.1) overlapping this one by > 20 %
  agree            number of the other prompts ("reef fish", "a fish") with a mask containing the dot
Model: class-weighted logistic regression on standardised features, leave-one-dive-out.
Reported: the coverage the gate buys at production's false-measurement rate.

Run from fishsense-lite's venv on CPU (needs cv2 + scipy):
  CUDA_VISIBLE_DEVICES= LD_LIBRARY_PATH=<libxcb> ../../../fishsense-lite/.venv/bin/python gate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from coverage import COV, load_masks  # noqa: E402

FEATS = ["score", "log_area", "elong", "silhouette", "solidity", "edge", "dot_axial", "dot_lateral", "n_masks", "agree"]


def features(m, x, y, score, others, agree):
    import cv2
    ys, xs = np.nonzero(m); area = len(xs)
    P = np.stack([xs, ys], 1).astype(float); c = P.mean(0)
    w, V = np.linalg.eigh(np.cov((P - c).T)); a = V[:, 1]
    proj = (P - c) @ a; L = proj.max() - proj.min()
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    hull = cv2.contourArea(cv2.convexHull(max(cnts, key=cv2.contourArea))) if cnts else area
    border = np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]])
    d = np.array([x, y]) - c
    overl = sum(1 for o in others if (o & m).sum() > 0.2 * min(area, o.sum()))
    return dict(score=score, log_area=np.log(area), elong=np.sqrt(w[1] / max(w[0], 1e-6)), silhouette=area / max(L, 1) ** 2,
                solidity=area / max(hull, 1), edge=border.mean(), dot_axial=abs(d @ a) / max(L / 2, 1),
                dot_lateral=abs(d @ np.array([-a[1], a[0]])) / max(L, 1), n_masks=overl, agree=agree)


def build():
    F = pd.read_csv(HERE / "frames.csv"); F = F[F.set == "reef"].set_index("image_id")
    lab = pd.read_csv(HERE / "measurability_labels.psv", sep="|").set_index("image_id")
    rows = []
    for p in sorted(COV.glob("*.npz")):
        iid = int(p.stem); r = F.loc[iid]; z = np.load(p); ox, oy = z["origin"]
        x, y = r.laser_x - ox, r.laser_y - oy; xi, yi = int(round(x)), int(round(y))
        sc, ms = load_masks(z, 0)
        hit = [(s, m) for s, m in zip(sc, ms) if m[yi, xi]]
        if not hit:
            continue
        s, m = max(hit, key=lambda t: t[0])
        agree = sum(any(mm[yi, xi] for mm in load_masks(z, k)[1]) for k in (1, 2))
        f = features(m, x, y, s, [o for o in ms if o is not m], agree)
        rows.append(dict(image_id=iid, dive=int(r.dive_id), green=str(r.laser_label).startswith("Green"),
                         measured=bool(pd.notna(r.head_x)), human_cat=lab.fish_measurable_category.get(iid, np.nan),
                         angle_cat=lab.fish_angle_category.get(iid, np.nan), curved_cat=lab.fish_curved_category.get(iid, np.nan), **f))
    return pd.DataFrame(rows)


def fit(X, y, lam=1e-2):
    n, d = X.shape; w = np.where(y == 1, n / (2 * y.sum()), n / (2 * (n - y.sum())))

    def f(t):
        z = X @ t[:d] + t[d]; p = 1 / (1 + np.exp(-z))
        loss = -(w * (y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12))).mean() + lam * (t[:d] ** 2).sum()
        g = w * (p - y) / n
        return loss, np.append(X.T @ g + 2 * lam * t[:d], g.sum())
    return minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B").x


def main():
    D = build(); D.to_csv(HERE / "gate_features.csv", index=False)
    C = pd.read_csv(HERE / "coverage_causes.csv")
    n_meas, n_skip = int(C.L_px.notna().sum()), int(C.L_px.isna().sum())
    print(f"candidates (a mask >= 0.1 contains the dot): {len(D)} = {D.measured.sum()} human-measured + {(~D.measured).sum()} human-skipped "
          f"(of {n_meas} / {n_skip} reef frames)")
    print("\nfeature means, measured vs skipped:"); print(D.groupby("measured")[FEATS].mean().T.round(3).to_string())
    X = D[FEATS].to_numpy(float); y = D.measured.to_numpy(int); prob = np.zeros(len(D))
    for dive in D.dive.unique():
        tr = (D.dive != dive).to_numpy(); te = ~tr
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        t = fit((X[tr] - mu) / sd, y[tr]); prob[te] = 1 / (1 + np.exp(-(((X[te] - mu) / sd) @ t[:-1] + t[-1])))
    D["p"] = prob
    auc = (prob[y == 1][:, None] > prob[y == 0][None, :]).mean()
    print(f"\nleave-one-dive-out AUC measured vs skipped: {auc:.3f}")
    # operating points; rates are over ALL reef frames of each kind, so they compare with the production row
    print("\n  gate                              | human-measured frames covered | human-skipped frames given a length")
    base = C.cause.eq("ok")
    print(f"  production (score > 0.5, no gate) | {base[C.L_px.notna()].mean():.1%} | {base[C.L_px.isna()].mean():.1%}")
    for thr in (0.3, 0.4, 0.5, 0.6, 0.7):
        acc = D.p > thr
        print(f"  gate p > {thr:.1f} on masks >= 0.1       | {(acc & D.measured).sum() / n_meas:.1%} | {(acc & ~D.measured).sum() / n_skip:.1%}")
    # the production-matched point: the largest coverage whose false rate does not exceed production's
    target = base[C.L_px.isna()].mean()
    best = max((t for t in np.linspace(0.05, 0.95, 91) if ((D.p > t) & ~D.measured).sum() / n_skip <= target), default=None, key=lambda t: ((D.p > t) & D.measured).sum())
    if best is not None:
        acc = D.p > best
        print(f"  at production's false rate (p > {best:.2f}) | {(acc & D.measured).sum() / n_meas:.1%} | {(acc & ~D.measured).sum() / n_skip:.1%}")
    s = D[~D.measured]
    print("\nwhy humans skipped the candidate frames (specieslabel), with mean gate p:")
    print(s.groupby(s.human_cat.fillna("(no species label)")).p.agg(["size", "mean"]).round(2).to_string())
    D.to_csv(HERE / "gate_features.csv", index=False)


if __name__ == "__main__":
    main()
