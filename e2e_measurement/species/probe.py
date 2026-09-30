"""Species probe, step 2 (CPU): a trained head on BioCLIP embeddings, leave-one-dive-out.

Classes: every FishSense species label present plus OTHER ("Identifiable but Nontarget"), so
non-target fish get a class instead of a threshold. Model: multinomial logistic regression,
L2 penalty, class-balanced weights, on the unit-normalised 1024-d BioCLIP image embedding
(optionally with the 13 zero-shot similarities appended). Fitted with scipy L-BFGS.

Evaluation is on the AUTOMATIC crops (SAM 3.1 mask box at the dot). Each dive is predicted by a
model trained on all other dives, using both their SAM and head/tail crops. The same fish
therefore never appears in both training and test. The penalty is fixed in advance
(LAMBDA); the grid is reported only as a sensitivity check.

Run on the GPU from coral-gardeners-fish-detector's venv (torch + CUDA):
  LD_LIBRARY_PATH=/run/opengl-driver/lib <repo>/.venv/bin/python probe.py [nested]
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
LAMBDA = 1e-2


def data():
    Z = np.load(HERE / "embeddings.npz")
    keys = Z["keys"]; X = Z["feats"]
    zs = Z["logit_scale"] * X @ Z["text"].T                       # zero-shot logits, 13 species
    F = pd.read_csv(HERE / "frames.psv", sep="|").set_index("image_id")
    truth = F.content.str.extract(r"\(([^)]+)\)")[0]
    truth[F.content.str.contains("Other")] = "OTHER"
    rows = pd.DataFrame(dict(key=keys, image_id=[int(k.split("_")[0]) for k in keys], variant=[k.split("_", 1)[1] for k in keys]))
    rows["truth"] = rows.image_id.map(truth); rows["dive"] = rows.image_id.map(F.dive_id)
    return rows, X, zs, list(Z["species"])


def fit(X, y, k, lam):
    """Class-weighted multinomial logistic regression with an L2 penalty.

    Full-batch L-BFGS in torch on the GPU when one is available (hundreds of fits in the nested
    loop); the same objective on CPU with scipy otherwise.
    """
    n, d = X.shape
    w = np.bincount(y, minlength=k).astype(float); w = np.where(w > 0, n / (k * np.maximum(w, 1)), 0.0)[y]
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        torch = None
    if torch is not None:
        Xt = torch.as_tensor(X, dtype=torch.float32, device=dev); yt = torch.as_tensor(y, device=dev)
        wt = torch.as_tensor(w, dtype=torch.float32, device=dev); wt = wt / wt.sum()
        W = torch.zeros(d, k, device=dev, requires_grad=True); b = torch.zeros(k, device=dev, requires_grad=True)
        opt = torch.optim.LBFGS([W, b], max_iter=500, tolerance_grad=1e-7, tolerance_change=1e-10, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            logp = torch.log_softmax(Xt @ W + b, dim=1)
            loss = -(wt * logp[torch.arange(n, device=dev), yt]).sum() + lam * (W ** 2).sum()
            loss.backward()
            return loss
        opt.step(closure)
        return W.detach().cpu().numpy().astype(float), b.detach().cpu().numpy().astype(float)
    from scipy.optimize import minimize
    Y = np.eye(k)[y]

    def f(theta):
        Wn = theta[: d * k].reshape(d, k); bn = theta[d * k:]
        L = X @ Wn + bn; L -= L.max(1, keepdims=True)
        P = np.exp(L); P /= P.sum(1, keepdims=True)
        loss = -(w * np.log(P[np.arange(n), y] + 1e-12)).sum() / w.sum() + lam * (Wn ** 2).sum()
        G = (P - Y) * w[:, None] / w.sum()
        return loss, np.concatenate([(X.T @ G + 2 * lam * Wn).ravel(), G.sum(0)])

    r = minimize(f, np.zeros(d * k + k), jac=True, method="L-BFGS-B", options=dict(maxiter=500))
    return r.x[: d * k].reshape(d, k), r.x[d * k:]


def lodo(rows, X, classes, lam):
    """Leave-one-dive-out predictions for every SAM crop."""
    cid = {c: i for i, c in enumerate(classes)}
    pred = pd.Series(index=rows.index, dtype=object); prob = pd.Series(index=rows.index, dtype=float)
    test = rows.variant == "sam"
    for dive in rows[test].dive.unique():
        tr = (rows.dive != dive) & rows.truth.notna(); te = test & (rows.dive == dive)
        W, b = fit(X[tr.to_numpy()], rows[tr].truth.map(cid).to_numpy(), len(classes), lam)
        L = X[te.to_numpy()] @ W + b; P = np.exp(L - L.max(1, keepdims=True)); P /= P.sum(1, keepdims=True)
        pred[te] = [classes[i] for i in P.argmax(1)]; prob[te] = P.max(1)
    return pred, prob


def report(name, t):
    tgt = t[t.truth != "OTHER"]; oth = t[t.truth == "OTHER"]
    hit = tgt.pred == tgt.truth
    per = hit.groupby(tgt.truth).mean()
    vote = tgt.groupby(["dive", "truth"]).pred.agg(lambda s: s.mode().iloc[0])
    print(f"\n== {name}: targets top-1 {hit.mean():.1%} (n={len(tgt)}), balanced {per.mean():.1%}; dive-vote {np.mean(vote.index.get_level_values('truth') == vote.values):.1%} ({len(vote)}); "
          f"Other recognised {np.mean(oth.pred == 'OTHER'):.1%} (n={len(oth)}); targets wrongly called Other {np.mean(tgt.pred == 'OTHER'):.1%}; "
          f"all 12-way {np.mean(t.pred == t.truth):.1%}")
    print("   per species:", {k: f"{v:.0%} (n={int((tgt.truth == k).sum())}, dives={tgt[tgt.truth == k].dive.nunique()})" for k, v in per.items()})


if __name__ == "__main__" and len(__import__("sys").argv) == 1:
    rows, X, zs, zs_species = data()
    classes = sorted(rows.truth.dropna().unique())
    ev = rows.variant == "sam"
    # zero-shot baseline on the same crops (13-way; OTHER never predicted)
    t0 = rows[ev].copy(); t0["pred"] = [zs_species[i] for i in zs[ev.to_numpy()].argmax(1)]
    report("zero-shot BioCLIP (baseline)", t0)
    for label, feats in (("probe on image embedding", X), ("probe on embedding + zero-shot scores", np.hstack([X, zs / 100.0]))):
        pred, prob = lodo(rows, feats, classes, LAMBDA)
        t = rows[ev].copy(); t["pred"] = pred[ev]; t["prob"] = prob[ev]
        report(f"{label}, lambda {LAMBDA}", t)
        if label.startswith("probe on image"):
            tgt = t[t.truth != "OTHER"]
            print("   confusion:"); print(pd.crosstab(tgt.truth, tgt.pred).to_string())
            t.to_csv(HERE / "probe_predictions.csv", index=False)
    print("\nsensitivity (image embedding): ", end="")
    for lam in (1e-3, 1e-2, 1e-1):
        pred, _ = lodo(rows, X, classes, lam); t = rows[ev].copy(); t["pred"] = pred[ev]; tg = t[t.truth != "OTHER"]
        print(f"lambda {lam}: {np.mean(tg.pred == tg.truth):.1%} / Other {np.mean(t[t.truth == 'OTHER'].pred == 'OTHER'):.1%};  ", end="")
    print()


def nested(rows, X, zs, zs_species, classes, lams=(1e-5, 1e-4, 1e-3, 1e-2)):
    """Leave-one-dive-out with lambda chosen by an inner leave-one-dive-out on the training dives only.

    Hybrid: for species the training dives barely cover (< MIN_DIVES dives), the class score is
    the zero-shot logit instead of the probe's -- the probe cannot learn what it has not seen.
    """
    MIN_DIVES = 2
    cid = {c: i for i, c in enumerate(classes)}; zmap = {s: i for i, s in enumerate(zs_species)}
    test = rows.variant == "sam"
    out = {k: pd.Series(index=rows.index, dtype=object) for k in ("probe", "hybrid")}; chosen = []

    def acc_of(tr_mask, te_mask, lam):
        W, b = fit(X[tr_mask.to_numpy()], rows[tr_mask].truth.map(cid).to_numpy(), len(classes), lam)
        return np.argmax(X[te_mask.to_numpy()] @ W + b, 1)

    for dive in rows[test].dive.unique():
        tr = (rows.dive != dive) & rows.truth.notna(); te = test & (rows.dive == dive)
        inner = []
        for lam in lams:                                     # inner LODO, training dives only
            hits = []
            for d2 in rows[tr & test].dive.unique():
                itr = tr & (rows.dive != d2); ite = tr & test & (rows.dive == d2)
                p = acc_of(itr, ite, lam); y = rows[ite].truth.map(cid).to_numpy()
                hits.append((p == y).mean())
            inner.append(np.mean(hits))
        lam = lams[int(np.argmax(inner))]; chosen.append(lam)
        W, b = fit(X[tr.to_numpy()], rows[tr].truth.map(cid).to_numpy(), len(classes), lam)
        L = X[te.to_numpy()] @ W + b
        out["probe"][te] = [classes[i] for i in L.argmax(1)]
        # hybrid: replace poorly covered species' scores with calibrated zero-shot logits
        cover = rows[tr].groupby("truth").dive.nunique()
        Lz = zs[te.to_numpy()]; H = L.copy()
        scale = L.std() / max(Lz.std(), 1e-6)
        for c in classes:
            if c != "OTHER" and cover.get(c, 0) < MIN_DIVES and c in zmap:
                H[:, cid[c]] = (Lz[:, zmap[c]] - Lz.mean(1)) * scale + L.mean(1)
        out["hybrid"][te] = [classes[i] for i in H.argmax(1)]
    return out, chosen


if __name__ == "__main__" and len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "nested":
    rows, X, zs, zs_species = data(); classes = sorted(rows.truth.dropna().unique()); ev = rows.variant == "sam"
    out, chosen = nested(rows, X, zs, zs_species, classes)
    print("lambda chosen per held-out dive:", pd.Series(chosen).value_counts().to_dict())
    for k, pred in out.items():
        t = rows[ev].copy(); t["pred"] = pred[ev]; report(f"nested-lambda {k}", t)
        t.to_csv(HERE / f"probe_{k}_predictions.csv", index=False)
