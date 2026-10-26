"""Figure fig:timeline (SenSys section 4): how the input was shaped for people over the collection period.

One panel, time axis 2023-08 .. 2025-01 (the collection period).
  bars     one stacked bar per month (all 525 dives; data/db_extracts/timeline_dives.psv,
           sql/extract_timeline_dives.sql) by laser color, red or green. A dive carries one laser, so its color is
           the majority color of its live (completed, not superseded) laser labels; the minority labels on 30 dives
           (51 of their 4,350 labels, 50 from the randomized labeling projects) are labeling errors. The 19 dives
           with images but no such label take FishSense's laser_colors (data/fishsense_api/laser_colors_unlabeled.csv:
           laser-stage predictions for 4, the unvalidated automatic dot color for 15). The 208 dives holding no
           canonical image hold byte-identical copies of other dives' images (data/db_extracts/duplicate_dives.psv,
           sql/extract_duplicate_dives.sql) and take those dives' color. Date: the camera clock, except the six dives whose
           clock disagrees with their deployment by more than 14 days (252, 253, 336, 337, 451, 452; FishSense
           API missions, data/fishsense_api/missions_lab.csv), which take the deployment date. Checked by eye:
           dive 253's dot is on a chevron slate (a 2024 pattern), dives 451/452 show red dots, dive 242 a green
           one. Each class has a color AND a fill: red solid dark red, green light green
           with hatching, so it reads in grayscale and for red-green colorblind
           readers (checked here: grayscale luminance and a deuteranopia simulation, Machado et al. 2009).
  shading  slate pattern (H, tic-tac-toe, chevron) behind the bars, one month at a time: a month is shaded when
           a dive in it is known to use a pattern, from dive.dive_slate_id (36 dives), a dive's calibration dive's
           slate (data/db_extracts/timeline_slate_links.psv, sql/extract_timeline_slate_links.sql, 15 more), or
           slate frames read by eye (analysis/codesign/slate_pattern_reads.csv, image ids listed). Months with no
           recorded pattern stay unshaded. One month holds two patterns: 2023-08 (H on 08-01..03, tic-tac-toe
           from 08-23), shaded half and half in date order; every other boundary is a month edge. One label per
           pattern, at the top, on the shaded month nearest the middle of its first to last shaded month. Field dive 45 (2023-08-17) has no
           slate and likely predates the slate procedure (the author, 2026-10-26). Checkerboard engineering
           tests are not marked (the author, 2026-10-26); their dives count in the bars.
Dates are tabulated by analysis/codesign/timeline_dates.py.

Writes analysis/codesign/figures/fig_timeline.{pdf,png} at 7 x 1.5 in, no title, no metadata, and
fig_timeline_{gray,deutan}.png previews (not for the paper).
Run: uv run python analysis/codesign/fig_timeline.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/figures"
W, H, FS = 7.0, 1.5, 7
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
RED, GREEN, GREEN_HATCH = "#a8322b", "#c4e8b8", "#3f7a37"
SHADE = {"H": "#dfe4eb", "tic-tac-toe": "#f3f5f8", "chevron": "#dfe4eb"}   # pale blue-grays; neighbors differ in lightness
T0, T1 = pd.Timestamp("2023-08-01"), pd.Timestamp("2025-02-01")
BAR_DAYS, YMAX = 24, 185
DEUTAN = np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]])  # Machado 2009, severity 1


def lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(c):
    return float(lin(to_rgb(c)) @ [0.2126, 0.7152, 0.0722])


def x(t):
    return mdates.date2num(pd.Timestamp(t))


def pattern(name):
    n = str(name)
    return "H" if n.startswith("H") else "tic-tac-toe" if n.startswith("Tic") else "chevron" if n.startswith("V") else None


def previews(png):
    """Grayscale and deuteranopia versions of the rendered PNG, to look at (not for the paper)."""
    img = plt.imread(png)[..., :3]
    L = lin(img)
    gray = (L @ [0.2126, 0.7152, 0.0722])
    gray = np.where(gray <= 0.0031308, gray * 12.92, 1.055 * gray ** (1 / 2.4) - 0.055)
    plt.imsave(OUT / "fig_timeline_gray.png", np.clip(gray, 0, 1), cmap="gray", vmin=0, vmax=1)
    d = np.clip(L @ DEUTAN.T, 0, 1)
    plt.imsave(OUT / "fig_timeline_deutan.png", np.clip(np.where(d <= 0.0031308, d * 12.92, 1.055 * d ** (1 / 2.4) - 0.055), 0, 1))


def main():
    # the two dive classes must differ in lightness (grayscale) and after a deuteranopia simulation; the shading
    # sits lighter than both bar fills, and neighboring shades differ in lightness
    sim = {k: lin(to_rgb(c)) @ DEUTAN.T for k, c in (("red", RED), ("green", GREEN))}
    assert luminance(RED) < 0.15 < luminance(GREEN) < 0.9, (luminance(RED), luminance(GREEN))
    assert abs(float(sim["red"] @ [0.2126, 0.7152, 0.0722]) - float(sim["green"] @ [0.2126, 0.7152, 0.0722])) > 0.3
    assert min(luminance(c) for c in SHADE.values()) > luminance(GREEN)
    assert luminance(SHADE["tic-tac-toe"]) - luminance(SHADE["H"]) > 0.1

    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None,
                    names="dive_id dive_datetime camera slate target images red green".split())
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True).dt.tz_localize(None)
    M = pd.read_csv(REPO / "data/fishsense_api/missions_lab.csv", parse_dates=["deployment_date"])[["dive_id", "deployment_date"]]
    D = D.merge(M, on="dive_id", how="left")
    clock_off = (D.t - D.deployment_date).abs() > pd.Timedelta(days=14)
    D.loc[clock_off, "t"] = D.loc[clock_off, "deployment_date"]   # camera clock wrong: take the deployment's date
    D["month"] = D.t.dt.to_period("M")
    lab = D.red + D.green
    D["laser"] = np.select([lab == 0, D.green > D.red], [None, "green"], "red")
    both = int(((D.red > 0) & (D.green > 0)).sum())
    api = pd.read_csv(REPO / "data/fishsense_api/laser_colors_unlabeled.csv").set_index("dive_id").color
    assert D.loc[D.dive_id.isin(api.index), "laser"].isna().all()
    D["laser"] = D.laser.fillna(D.dive_id.map(api))
    dup = pd.read_csv(REPO / "data/db_extracts/duplicate_dives.psv", sep="|", header=None, names=["dive_id", "src", "n"])
    dup["color"] = dup.src.map(D.set_index("dive_id").laser)
    inherit = dup.groupby("dive_id").color.agg(lambda s: s.iloc[0] if s.nunique() == 1 else "conflict")
    assert inherit.notna().all() and (inherit != "conflict").all(), inherit[inherit.isna() | (inherit == "conflict")]
    D["laser"] = D.laser.fillna(D.dive_id.map(inherit))
    assert D.laser.notna().all(), D[D.laser.isna()].dive_id.tolist()
    months = pd.period_range("2023-08", "2025-01", freq="M")
    per = D.groupby(["month", "laser"]).size().unstack(fill_value=0).reindex(months, fill_value=0)
    for c in ("red", "green"):
        if c not in per:
            per[c] = 0
    mid = np.array([x(m.start_time + pd.Timedelta(days=15)) for m in months])

    # slate pattern per month: every month in which a dive is known to use it
    known = D.assign(pattern=D.slate.map(pattern))[["t", "pattern"]].dropna()
    link = pd.read_csv(REPO / "data/db_extracts/timeline_slate_links.psv", sep="|", header=None, names=["dive_id", "slate"])
    link = link.merge(D[["dive_id", "t"]], on="dive_id").assign(pattern=lambda d: d.slate.map(pattern))[["t", "pattern"]]
    reads = pd.read_csv(REPO / "analysis/codesign/slate_pattern_reads.csv", parse_dates=["date"]).query("pattern != 'unreadable'")
    reads = reads.rename(columns={"date": "t"}).assign(pattern=lambda d: d.pattern.replace({"chevron (V)": "chevron"}))
    known = pd.concat([known, link, reads[["t", "pattern"]]])
    known["month"] = known.t.dt.to_period("M")
    first = known.groupby(["month", "pattern"]).t.min().reset_index().sort_values(["month", "t"])
    shades = []                          # (start, end, pattern); a month with two patterns is split evenly in date order
    for m, g in first.groupby("month"):
        a, b = m.start_time, (m + 1).start_time
        step = (b - a) / len(g)
        shades += [(a + i * step, a + (i + 1) * step, p) for i, p in enumerate(g.pattern)]
    two = first.groupby("month").size()
    assert two[two > 1].index.astype(str).tolist() == ["2023-08"], two[two > 1]

    plt.rcParams.update({"font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
                         "axes.edgecolor": MUTED, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
                         "hatch.linewidth": 0.6, "pdf.fonttype": 42, "savefig.bbox": "standard"})
    fig, ax = plt.subplots(figsize=(W, H), layout="constrained")

    for a, b, p in shades:
        ax.axvspan(x(a), x(b), color=SHADE[p], lw=0, zorder=0)
    for p, g in pd.DataFrame(shades, columns=["a", "b", "p"]).groupby("p"):   # label on the shaded piece nearest the era's middle
        c = g.a + (g.b - g.a) / 2
        at = c.iloc[(c - (g.a.min() + (g.b.max() - g.a.min()) / 2)).abs().argmin()]
        ax.text(x(at), YMAX * 0.97, p, ha="center", va="top", color=INK2, fontsize=FS, zorder=1)

    style = {"red": dict(color=RED, edgecolor=RED, lw=0.6),
             "green": dict(color=GREEN, edgecolor=GREEN_HATCH, hatch="//////", lw=0.6)}
    bottom = np.zeros(len(months))
    for c in ("red", "green"):
        v = per[c].to_numpy(float)
        ax.bar(mid[v > 0], v[v > 0], width=BAR_DAYS, bottom=bottom[v > 0], zorder=2, **style[c])   # empty bars would still draw an outline
        bottom += v
    ax.set_ylim(0, YMAX); ax.set_yticks([0, 50, 100, 150])
    ax.set_ylabel("dives", rotation=0, ha="right", va="center", labelpad=4, color=INK2)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=1)

    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[2, 5, 8, 11]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y")); ax.xaxis.set_minor_locator(mdates.MonthLocator())
    ax.tick_params(axis="x", which="minor", length=2, color=MUTED); ax.tick_params(axis="x", which="major", length=3, color=MUTED)
    ax.set_xlim(x(T0), x(T1))

    key = [Patch(facecolor=RED, edgecolor=RED, label="red laser"),
           Patch(facecolor=GREEN, edgecolor=GREEN_HATCH, hatch="//////", label="green laser")]
    fig.legend(handles=key, loc="outside upper center", ncol=2, frameon=False, handlelength=1.4, handleheight=0.9, columnspacing=1.2, borderaxespad=0.1)

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "fig_timeline.pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "fig_timeline.png", dpi=300, metadata={"Software": None})
    previews(OUT / "fig_timeline.png")
    print("wrote fig_timeline; dives re-dated from deployment:", sorted(D.loc[clock_off, "dive_id"]), "; dives with minority-color labels:", both, "; dives by class:", D.laser.value_counts().to_dict(),
          "; shaded months:", {p: sorted({str(pd.Timestamp(a).to_period('M')) for a, _, q in shades if q == p}) for p in SHADE})


if __name__ == "__main__":
    main()
