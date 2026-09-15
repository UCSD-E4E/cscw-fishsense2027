# P2 handoff — deployability for citizen scientists, 2026-09-12

Written for: an agent starting P2 (the CSCW deployability paper) with no access to the
sessions that produced this.

**Status: nothing here is analyzed yet.** This repo holds scope, dependencies and
blockers, established in a scoping review on 2026-09-12 against the P1 corpus. It is
deliberately not a findings document — there are no P2 findings. §5 is the work queue.

Sibling repos are listed in `README.md`; this document cites them by relative path. Before
touching any FishSense data, read
`../imwut_2026_fishsense_lite/post_labeling_analysis/HANDOFF.md` §0 — its ground rules were
learned the hard way and §3 below repeats the one P2 is most likely to break.

---

## 0. What P2 is, and what it is not

**Claim.** System characterization is not deployment. P2 identifies the barriers between a
validated instrument and self-service adoption by untrained recreational divers, and
quantifies how far each can be removed.

**Scope boundary, load-bearing.** The existing REEF deployment involved *trained volunteers
operating inside a structured scientific program*. That population is not a proxy for
unsupported recreational use. P2 must say so explicitly and treat a study of the
unsupported case as future work. Do not let a reviewer — or a draft — quietly promote REEF
volunteers into "citizen scientists with no training."

**Not P2:** the refraction model and in-air calibration (P4, `../wuwnet-fishsense2026`);
the accuracy characterization (P1, `../imwut_2026_fishsense_lite`); the detector
*architecture* question (§4.3, currently unassigned to any paper).

---

## 1. The barriers, and who owns each

| barrier | owner | state |
|---|---|---|
| specialty optics (Backscatter M52 air lens) | P4 | removed by the refractive model |
| calibration performed at depth | P4 | moved in-air by P4 |
| calibration target must be fabricated by measurement | **P2** | proposed: commodity interlocking-brick target, graded against P4's checkerboard. **Blocked — §4.1** |
| post-dive annotation burden | **P2** | shared head/tail detector + laser-dot detection, graded against inter-annotator agreement. **Blocked — §4.2** |
| mount manufacture, printability, dimensional stability | **P2** | not started |
| hardware specificity (one camera model) | **P2** | not started |

---

## 2. What P1 and P4 must supply before P2 can start

P2 grades two replacements (brick target, automatic annotation) against two baselines
(P4's checkerboard, the human labeler). Both baselines belong to other papers, and neither
is pinned yet.

**Proposed in the 2026-09-12 scoping review, not yet adopted:** P1 defines the *acceptance
test* for a calibration — the contract the laser extrinsics must satisfy — rather than
describing a procedure. P4 and P2 then become alternative implementations certified against
that one test. If adopted this disposes of the publication plan's open question 3 (a shared
error metric between P4 and P2) structurally rather than by negotiation, and it means P1's
preprint must land before P4 fixes its evaluation.

The test itself already exists and is scale-free: a rigid object must read the same length
at every range, so the Theil–Sen slope of length against laser depth estimates the in-plane
calibration error with **no reference length spent**. Implementation and constants:
`../imwut_2026_fishsense_lite/fishsense_imwut/calibration.py` (`range_trend`,
`range_trend_flagged_dives`), ported from fishsense-lite's `range_trend.py`. Rationale and
sensitivity: `../imwut_2026_fishsense_lite/post_labeling_analysis/HANDOFF.md` §3.1.

---

## 3. Why the reference-length route is closed

Repeated from the P1 handoff §0 because P2 will be tempted by it: **known lengths are the
validation set, never a calibration source.** Anything that fits a calibration to the models
and then grades it on the models is circular. If P2 grades a brick target by measuring fish
models with it, the number means nothing. Use the scale-free test in §2.

---

## 4. Blockers, in the order they will hurt

### 4.1 The checkerboard baseline carries an unquantified systematic

P2's brick target is graded against P4's checkerboard. But the checkerboard has a **±1.2 %
pitch tolerance** (E4E board, 14×10 interior corners, 42 mm pitch), and in the P1 corpus
the checkerboard-calibrated sessions sit ~1.5 pp below the slate-calibrated ones — a gap
that is **not identifiable**, because the two groups share no target, so calibration method
is perfectly confounded with target set
(`../imwut_2026_fishsense_lite/post_labeling_analysis/HANDOFF.md` §6.3).

If P4 ships a baseline with an unquantified systematic, P2's degradation number inherits it
and means nothing. Either the target comparison runs **once, in one paper, over a shared
target set**, or P4 quantifies its own baseline first. This is a scope decision between P4
and P2 and should be made before P4 is submitted.

### 4.2 The human ceiling does not exist

The publication plan describes the detector as "evaluated against *measured*
inter-annotator agreement as the human ceiling." **It is not measured.** Verified
2026-09-12 against `../imwut_2026_fishsense_lite/laser_labeling_analysis/`:

- `laser_labels_cleaned.csv` — 37,811 rows over 262 dives, exactly one label per image
  (`image_id` is unique; 0 images carry more than one). Red Laser 31,841, Green Laser
  5,970. **No repeat labels, so no agreement can be computed from it.**
- No inter-annotator agreement analysis exists anywhere in that repository.

You cannot claim a detector reaches the human ceiling without the ceiling. Prod may hold a
partial source — `laserlabel` keeps `superseded` rows and never deletes them, and a dive
can carry two live labels on one image — but superseding is *correction*, not independent
annotation, so treat it as a lower bound on disagreement at best. The real study is two
annotators over a few hundred frames, and it is far cheaper to collect before the defense
(December 2026) than after.

### 4.3 The detector has no home inside the dissertation

The publication plan calls the shared head/tail detector "the technical through-line
linking the two platforms," but its only paper homes are P2 (post-defense) and P3's
fallback (data-risked). Combined with §4.2, the entire annotation axis of the work
currently sits outside the dissertation body. Flagged in the 2026-09-12 scoping review as a
structural gap to resolve at the plan level, not here.

The plan's open question 6 — one model spanning both domains, or the same architecture
trained per platform — determines whether the contribution is *domain robustness* or
*keypoint formulation*. It is unanswered and it changes what P2 claims.

---

## 5. Work queue

1. **Bound the landmark-placement error from the P1 corpus, no new labeling.** A rigid
   target photographed repeatedly at one range must read one length. Within a
   (session, target, narrow range bin) the frame-to-frame spread is landmark noise +
   ranging noise + pose; pose is one-sided, so the spread among the *best-presented* frames
   bounds landmark noise. Computable today from
   `../imwut_2026_fishsense_lite/fish_model_analysis/data/corpus.csv`. This is not the
   inter-annotator ceiling — it is a cheap upper bound on one labeler's placement noise —
   but it is enough to put a number behind P1's claim that the near-range Weasly Fish bias
   (−6.8 % below 0.8 m against the Box's −2.3 % at the same ranges) is a landmark effect
   rather than ranging (P1 handoff §6.4). Land it in `annotation_analysis/`.
2. **Settle §4.1** with P4: who runs the target comparison, over which targets.
3. **Collect the inter-annotator study** (§4.2) — two annotators, a few hundred frames,
   before the defense.
4. **Resolve §4.3** at the publication-plan level.
5. Mount printability and hardware specificity — not started, no blockers known.

---

## 6. Conventions

`uv sync`, then `uv run` everything from the repository root. Analysis notebooks live in
`<topic>_analysis/` folders, matching `../imwut_2026_fishsense_lite` and
`../wuwnet-fishsense2026`.

**Nothing from the IMWUT repo is vendored; this repo reads it by relative path, so the two
must sit side by side.** Three things cross the boundary:

| what | where it lives | how this repo reaches it |
|---|---|---|
| the measurement corpus (`corpus.csv`) | IMWUT | relative path |
| `laser_labels_cleaned.csv` (37,811 labels) | IMWUT — it is an input to that repo's bundle-adjustment simulation | relative path, set in `annotation_analysis/laser_label_analysis.ipynb` |
| `fishsense_imwut.calibration.load_rows` | IMWUT | `sys.path`, for §5 item 1 — see below |

`sys.path` rather than a uv path dependency is deliberate and explained in `pyproject.toml`:
the IMWUT repo depends on `fishsense-meta` (git), which needs a C/Rust toolchain and is why
that repo carries a `flake.nix`. Declaring it as a path source makes `uv sync` here fail
outright. `calibration.py` is pure numpy/scipy, so importing it that way pulls in nothing
heavy:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent.parent / "imwut_2026_fishsense_lite"))
from fishsense_imwut import calibration as cal
```

**What is *not* here:** the pixel-error → reconstruction-error sensitivity study. It briefly
moved here with the rest of `labeling_analysis/`, on the reading that "what pixel accuracy
must an annotator hit" is P2's contract question. It went back, as
`../imwut_2026_fishsense_lite/reconstruction_analysis/pixel_sensitivity.ipynb`: by content
it is a reconstruction simulation on the same synthetic harness as that repo's others, and
P1's error budget is what cites it. P2 still *uses* its result — the tolerable pixel
displacement per range is the acceptance criterion a detector has to meet — so cite the
number, do not rebuild the study.

The cost of not vendoring is that this repo's results move when the IMWUT corpus is
re-pulled. If P2 needs a frozen snapshot for a submission, copy it into `data/` at that
point and record which commit of the IMWUT repo it came from.

Corpus CSVs are `|`-delimited with JSON geometry columns; read them with
`fishsense_imwut.calibration.load_rows`, not bare `csv.reader`.

Prod is read-only from the analysis environment and **prod writes are the user's** — write
the SQL, hand it over, verify afterwards read-only. The read-only psql recipe and the
NAS/Garage layout are in the P1 handoff §1.

---

## 7. P4 → P2 note, 2026-09-13: the laser needs no target

Written after P4's per-dive laser work (`../wuwnet-fishsense2026/fishsense_wuwnet/laser.py`,
`refraction_analysis/laser_per_dive.ipynb`) and a check of it on the P1 corpus
(`annotation_analysis/scalefree_laser_selfcal.ipynb` here). It changes §1 and §2 and
gives §4.1 an experiment; it does not touch §4.2/§4.3.

**The result.** The in-plane laser angle φ — invisible to the dots, per P1 §3.3 — is
recoverable with no known length from any rigid object the dot lands on in two or more
frames at different ranges: apparent size is ∝ 1/Z, so dot position along the locus is
linear in apparent size and the intercept is the beam's vanishing point. P4 calls this
Tier 3 (`close_with_apparent_size`). On the P1 corpus it reproduces P1's known-length
calibration (`fit_phi_joint`) to **0.003° median / 0.016° MAD over ten Box dives**, and it
is biased on solid fish models by exactly P1's half-thickness parallax (§6.4 there),
ordering by `b`. So the size must be measured at the dot's surface — body height at the
dot, or a slab.

**§1 rows affected.**
- *calibration target must be fabricated by measurement*: for the laser, no target at
  all. The checkerboard survives only for the camera, in air, once per unit (P4). A brick
  target is a slab, so for the laser it needs no known dimension — the laser half of the
  §4.1 grading disappears rather than needing to be run.
- *calibration performed at depth*: the slate leaves the dive; the dive's own rigid
  objects are the calibration.
- *mount dimensional stability*: quantified. Worst-case 15 % on length needs `|O|` to
  15 mm and nothing on `D` (self-calibrated per dive). Any printed mount meets 15 mm.

**§2, the acceptance test.** Tier 3 is P1's range-trend statistic used as the estimator
instead of the residual — same physics, same rigidity assumption, no known length. The
guardrail P2 must state: **calibrate on one object, test on another**; an object used
for Tier 3 passes `range_trend` on itself by construction.

**§4.1.** The gap experiment (recalibrate every dive target-free, see if the
checkerboard-vs-slate gap survives) is set up in the notebook but *not* clean on this
corpus: the two groups carry different model sets with different parallax. It needs a
parallax-free size on both sides. Two things P2 should carry into that discussion
regardless: an in-air calibration on the E4E board carries a 0.7 % fx/fy anisotropy of
unresolved origin, and P1 has since shown it is **fleet-wide** — all seven production
cameras read fx/fy = 0.99141 ± 0.00044, never straddling 1. It is therefore **not** a
candidate for the checkerboard-vs-slate gap: it is common to both groups, so it cannot
make a difference between them, and §6.3's "systematic in corner detection" stays open
with this not being it. It is still P2's business for another reason. The leading
hypothesis is that the E4E board's *printed pitch* is anisotropic — inside the ±1.2 %
tolerance §4.1 already quotes, with printer feed-axis scaling as the mechanism — and both
P4's and production's code model the pitch as a single scalar `square_size_m`, which
cannot express it. If that is the cause, a moulded brick target is *better* than a printed
board on this axis, and the fix elsewhere is to caliper targets per axis on receipt.
Undecided until one unit is calibrated landscape and portrait; the exchange is P1's
`p4_reply_anisotropy.md` and P4's `p4_response_anisotropy.md`. Separately, P1's SAM3
head/tail stage segments the P4 decoy cleanly, so the annotation barrier and this
calibration share a backend.

**For P1, not P2:** thickness parallax puts a genuine positive range trend on solid models
under a *correct* calibration — `length(z) = L + b/z`, so the Theil-Sen pairwise slope is
`-b/(z_i z_j)`, always positive for `b < 0`. Computed per corpus cell against P1's own
gates: Box +0.4 to +0.9 %/m, Weasly Fish +0.9 to +2.3 %/m, the one Snook cell +2.4 %/m,
against a 2.0 %/m flag — 4 of 22 cells at or over it on parallax alone. No Grouper cell
passes the gates. Small next to the observed spread (-6 to +5.5 %/m), so it is a one-sided
bias on the audit statistic rather than its dominant term, but not zero, and the Box is
the only model free of it.
