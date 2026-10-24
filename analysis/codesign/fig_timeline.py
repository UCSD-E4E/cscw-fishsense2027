"""Figure fig:timeline (SenSys section 4): how the input was shaped for people over the collection period.

Time axis 2023-08 .. 2025-01 (the collection period). Two lanes:
  dives   one stacked bar per month (all 525 dives, camera clock; data/db_extracts/timeline_dives.psv,
          sql/extract_timeline_dives.sql) by laser color: red, green, or no color recorded (no completed laser
          label with a dot). A dive's color is the majority color of its laser labels (>= 90% one color for
          all but 12 mixed dives). Each class has a color AND a fill: red solid dark red, green light green
          with hatching, unknown white outline only, so it reads in grayscale and for red-green colorblind
          readers (checked here: grayscale luminance and a deuteranopia simulation, Machado et al. 2009).
  slate   H, tic-tac-toe, chevron (V), each from the first to the last dive known to use it, breaking at months
          with no dives: dive.dive_slate_id (36 dives), a dive's calibration dive's slate
          (data/db_extracts/timeline_slate_links.psv, sql/extract_timeline_slate_links.sql, 15 more), slate frames
          read by eye (analysis/codesign/slate_pattern_reads.csv, image ids listed). Hatched: field dives whose
          pattern is unrecorded (2023-08-17, 2024-02-28). Orange: checkerboard engineering tests, 2023-08-14..18
          (dive.calibration_target_id) and 2025-01-17 (TG-7 sessions; analysis/codesign/timeline.yaml).
One key row; direct labels only for the slate pattern names. Dates are tabulated by
analysis/codesign/timeline_dates.py.

Writes analysis/codesign/figures/fig_timeline.{pdf,png} at 7 x 1.6 in, no title, no metadata, and
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
from matplotlib.patches import Patch, Rectangle

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/figures"
W, H, FS = 7.0, 1.6, 7
BLUE, ORANGE = "#2a78d6", "#eb6834"                     # reference palette slots 1-2 (slate, checkerboard)
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
RED, GREEN, GREEN_HATCH = "#a8322b", "#c4e8b8", "#3f7a37"
T0, T1 = pd.Timestamp("2023-08-01"), pd.Timestamp("2025-02-01")
CB_TESTS = [("2023-08-14", "2023-08-18"), ("2025-01-17", "2025-01-17")]
BAR, MIN_DAYS, BAR_DAYS = 0.62, 4, 24
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
    return "H" if n.startswith("H") else "tic-tac-toe" if n.startswith("Tic") else "chevron (V)" if n.startswith("V") else None


def pieces(a, b, empty):
    """[a, b) split around months with no dives, so those months stay blank."""
    out, cur, b = [], pd.Timestamp(a), pd.Timestamp(b)
    for m in sorted(empty):
        s, e = m.start_time, (m + 1).start_time
        if s < b and e > cur:
            if s > cur:
                out.append((cur, s))
            cur = max(cur, e)
    if cur < b:
        out.append((cur, b))
    return out


def lane_box(ax, a, b, **kw):
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    if (b - a).days < MIN_DAYS:
        b = a + pd.Timedelta(days=MIN_DAYS)
    ax.add_patch(Rectangle((x(a), -BAR / 2), x(b) - x(a), BAR, **kw))
    return a, b


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
    # the three dive classes must differ in lightness (grayscale) and after a deuteranopia simulation
    sim = {k: lin(to_rgb(c)) @ DEUTAN.T for k, c in (("red", RED), ("green", GREEN), ("unknown", "#ffffff"))}
    assert luminance(RED) < 0.15 < luminance(GREEN) < 0.9, (luminance(RED), luminance(GREEN))
    assert abs(float(sim["red"] @ [0.2126, 0.7152, 0.0722]) - float(sim["green"] @ [0.2126, 0.7152, 0.0722])) > 0.3

    D = pd.read_csv(REPO / "data/db_extracts/timeline_dives.psv", sep="|", header=None,
                    names="dive_id dive_datetime camera slate target images red green".split())
    D["t"] = pd.to_datetime(D.dive_datetime, utc=True).dt.tz_localize(None); D["month"] = D.t.dt.to_period("M")
    E = pd.read_csv(REPO / "data/db_extracts/dive_environment.psv", sep="|", header=None, names=["dive_id", "env"])
    D = D.merge(E, on="dive_id", how="left")
    lab = D.red + D.green
    D["laser"] = np.select([lab == 0, D.green > D.red], ["unknown", "green"], "red")
    mixed = int(((lab > 0) & (D.red < 0.9 * lab) & (D.green < 0.9 * lab)).sum())
    months = pd.period_range("2023-08", "2025-01", freq="M")
    per = D.groupby(["month", "laser"]).size().unstack(fill_value=0).reindex(months, fill_value=0)
    for c in ("red", "green", "unknown"):
        if c not in per:
            per[c] = 0
    empty = [m for m in months if per.loc[m].sum() == 0]
    mid = np.array([x(m.start_time + pd.Timedelta(days=15)) for m in months])

    plt.rcParams.update({"font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
                         "axes.edgecolor": MUTED, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
                         "hatch.linewidth": 0.6, "pdf.fonttype": 42, "savefig.bbox": "standard"})
    fig, (dx, sx) = plt.subplots(2, 1, figsize=(W, H), sharex=True, layout="constrained", gridspec_kw=dict(height_ratios=[2.2, 0.75]))

    # lane 1: dives per month, stacked red / green / unknown
    style = {"red": dict(color=RED, edgecolor=RED, lw=0.6),
             "green": dict(color=GREEN, edgecolor=GREEN_HATCH, hatch="//////", lw=0.6),
             "unknown": dict(color="white", edgecolor=INK2, lw=0.6)}
    bottom = np.zeros(len(months))
    for c in ("red", "green", "unknown"):
        v = per[c].to_numpy(float)
        dx.bar(mid, v, width=BAR_DAYS, bottom=bottom, **style[c])
        bottom += v
    dx.set_ylim(0, 160); dx.set_yticks([0, 50, 100, 150])
    dx.set_ylabel("dives", rotation=0, ha="right", va="center", labelpad=4, color=INK2)
    dx.grid(axis="y", color=GRID, lw=0.6); dx.set_axisbelow(True)

    # lane 2: slate pattern; hatched = field dives with the pattern unrecorded; orange = checkerboard tests
    known = D.assign(pattern=D.slate.map(pattern))[["t", "pattern"]].dropna()
    link = pd.read_csv(REPO / "data/db_extracts/timeline_slate_links.psv", sep="|", header=None, names=["dive_id", "slate"])
    link = link.merge(D[["dive_id", "t"]], on="dive_id").assign(pattern=lambda d: d.slate.map(pattern))[["t", "pattern"]]
    reads = pd.read_csv(REPO / "analysis/codesign/slate_pattern_reads.csv", parse_dates=["date"]).query("pattern != 'unreadable'")
    known = pd.concat([known, link, reads.rename(columns={"date": "t"})[["t", "pattern"]]]).groupby("pattern").t.agg(["min", "max"])
    spans = {p: (known.loc[p, "min"].normalize(), known.loc[p, "max"].normalize() + pd.Timedelta(days=1)) for p in known.index}
    for p, (a, b) in spans.items():
        parts = pieces(a, b, empty)
        for pa, pb in parts:
            lane_box(sx, pa, pb, fc=BLUE, ec="white", lw=1.0)
        if p != "H":     # H spans three days: its name sits above the lane instead
            widest = max(parts, key=lambda q: q[1] - q[0])
            sx.text(x(widest[0] + (widest[1] - widest[0]) / 2), 0, p, va="center", ha="center", color="white", fontsize=FS)
    order = sorted(spans.items(), key=lambda kv: kv[1][0])
    for (_, (_, b0)), (_, (a1, _)) in zip(order, order[1:]):
        if len(D[(D.t >= b0) & (D.t < a1) & (D.env == "reef")]):
            for pa, pb in pieces(b0, a1, empty):
                lane_box(sx, pa, pb, fc="white", ec=MUTED, lw=0.6, hatch="////")
    for a, b in CB_TESTS:
        lane_box(sx, a, pd.Timestamp(b) + pd.Timedelta(days=1), fc=ORANGE, ec="white", lw=0.6, zorder=3)
    h0 = spans["H"]
    sx.text(x(h0[0]), BAR / 2 + 0.05, "H", va="bottom", ha="left", color=INK, fontsize=FS)
    sx.set_ylim(-0.55, 0.9); sx.set_yticks([])
    sx.set_ylabel("slate", rotation=0, ha="right", va="center", labelpad=4, color=INK2)

    for a in (dx, sx):
        for s in ("top", "right", "left"):
            a.spines[s].set_visible(False)
        a.spines["bottom"].set_visible(a is dx); a.spines["bottom"].set_color(MUTED)
        a.tick_params(axis="y", length=0)
    dx.tick_params(axis="x", which="both", length=0)
    sx.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[2, 5, 8, 11]))
    sx.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y")); sx.xaxis.set_minor_locator(mdates.MonthLocator())
    sx.tick_params(axis="x", which="minor", length=2, color=MUTED); sx.tick_params(axis="x", which="major", length=3, color=MUTED)
    sx.set_xlim(x(T0), x(T1))

    key = [Patch(facecolor=RED, edgecolor=RED, label="red laser"),
           Patch(facecolor=GREEN, edgecolor=GREEN_HATCH, hatch="//////", label="green laser"),
           Patch(facecolor="white", edgecolor=INK2, label="laser color unknown"),
           Patch(facecolor="white", edgecolor=MUTED, hatch="////", label="pattern unrecorded"),
           Patch(facecolor=ORANGE, edgecolor=ORANGE, label="checkerboard (engineering tests)")]
    fig.legend(handles=key, loc="outside upper center", ncol=5, frameon=False, handlelength=1.4, handleheight=0.9, columnspacing=1.2, borderaxespad=0.1)

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "fig_timeline.pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "fig_timeline.png", dpi=300, metadata={"Software": None})
    previews(OUT / "fig_timeline.png")
    print("wrote fig_timeline; mixed dives assigned by majority:", mixed, "; dives by class:", D.laser.value_counts().to_dict(),
          "; luminance red/green:", round(luminance(RED), 3), round(luminance(GREEN), 3))


if __name__ == "__main__":
    main()
