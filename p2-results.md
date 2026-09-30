# P2 tier-0 results — 2026-09-23; T1/T2 2026-09-24; T3 2026-09-25

## What P2 is: two pillars (set 2026-09-25)

P2 has the same logic as P4: **high friction makes the system less likely to be used.**
It removes the two biggest sources of friction left after P4:

1. **The per-dive laser calibration.**
2. **The human labels:** laser dot, snout and fork.

Everything below is filed under one of them or marked as supporting.

### Why: the one outside partner left over exactly these costs

REEF, the only outside deployment partner, stopped using FishSense Lite because its data
could not be processed quickly. They cited the per-dive calibration among the reasons,
and moved to a custom-machined parallel dual-laser caliper on a GoPro. It needs no
calibration because the lasers' geometry is fixed in manufacture: fabrication
accessibility traded for zero calibration. (Source: project lead, 2026-09-25. REEF's own account
is not yet on record.)

The turnaround REEF experienced, reconstructed from label timestamps
(`fishsense_cscw/turnaround.py`, `tests/test_turnaround.py`):

| REEF dives (243) | median | p10–p90 |
|---|---|---|
| **dive → measurable** (laser + head/tail first-pass labels 90 % done) | **773 days** | 272–982 |
| dive → data at the lab (dated "REEF Data Dump" folders) | 227 days | 9–455 |
| data at the lab → measurable | 521 days (2023 dives 532, 2024 dives 285) | 137–816 |

**105 of 243 REEF dives (43 %) are still not measurable.** "Measurable" ignores species
and calibration, so these are lower bounds. The folder-date split is approximate, and
2023 dives waited on a pipeline that was still being built.

**The fair comparison with REEF's caliper:** the caliper also needs a human to mark two
dots, the snout and the fork. So REEF's gain came mainly from dropping calibration, and
"automation would have kept REEF" is not a claim P2 can make. P1's Table 1 rates calipers
at 12 % error and $600 against FishSense's 15 % and $1,040. P2 has to say what FishSense
offers in return (a single laser, fish smaller than the caliper baseline, recovered range)
*and* show that its calibration burden can come down to caliper level.

### E1 — label-free laser calibration (2026-09-25)

Production's stage-13 code and refusal gates, on P1's 23 calibration dives, scored
against known lengths. `calibration_analysis/e1_label_free/README.md`, pinned by
`tests/test_e1.py`.

| | dives | accepted | refused | accepted but >2 pp off | median p90 error |
|---|---|---|---|---|---|
| **checkerboard, fully label-free** | 11 | **11** | 0 | **0** | 2.17 % (same as with human dots) |
| slate, human corners + detector dots | 12 | 9 | 3 | **0** | 3.25 % |
| slate, predicted corners + detector dots | 12 | 6 | 6 | 2 | 2.38 % |

**The laser dot is automatable in calibration today**: detector dots fail closed and
are never silently wrong. **The human step is the duct-tape slate's corners.** The
checkerboard dives show the kernel and gates work end to end when corners come free,
but a printed target reintroduces what P4 removed, and the duct-tape slate is kept
because it is approachable. So the work goes into the slate: fewer labelled frames
(the lever arm pins the fit, not the count), a better duct-tape corner finder, or no
slate at all (E1c). Limits: pool only, red lasers, 2023 dives.

### Coverage: how many dives could calibrate from their own dots (2026-09-26)

`fishsense_cscw/coverage.py`, pinned by `tests/test_coverage.py`. Each dive is simulated
with its **real** dot count and reconstructed range spread, under E1g's size + brightness
fit and noise assumptions. *Conditional on E1g passing* (dimmed laser, so dots are
unclipped).

| | reaches the 0.05° target | usable, 0.05–0.15° (≤ ~4.5 % of length at 2 m) | not usable | share of dots usable or better |
|---|---|---|---|---|
| **per dive** (255 dives) | 21 | 167 | 67 | **94 %** |
| **pooled** (179 units) | 54 | 166 | 35 | **98 %** |
| REEF field, per dive / pooled (188) | 16 / 21 | 111 / 133 | 61 / 34 | |

- **Dot count decides it, not range.** Target dives have a median ~244 dots, usable ones
  ~74, failing ones ~11. The range spread is similar across all three, so the failing dives
  are the ones with little to measure.
- **Pooling** joins consecutive same-camera, same-day dives whose dot lines agree to 5 px:
  255 dives become 179 units, with 131 dives in multi-dive units. It lifts the target tier
  from 21 to 54 dives, and failing dives fall to 2 % of dots. The line only sees part of a
  mount shift (11–23 % of harmful shifts are invisible to it), so pooled numbers are an
  upper bound.
- **Detector recall of 0.82** instead of every labelled dot changes little
  (per dive 19 / 158 / 78; pooled 56 / 139 / 60).
- **Not assessed:** 43 dives, on cameras with no stored calibration (the TG-7 units) or
  with fewer than 5 dots.
- **Caveats:**
  - The noise is assumed (width 0.3 px, divergence ±0.05 px, absorption 30 % off,
    reflectance ×1.35).
  - Ranges are reconstructed: exact in shape, −22 % to +9 % in scale.
  - Dives near 0.05° flip class with the random draw, so read the target tier as ±~10.

### Status by pillar

| | measured | missing (core experiment) |
|---|---|---|
| **1. calibration** | intrinsics in air (P4); scale-free self-calibration on the pool Box, 0.003° median; **E1: detector dots fail closed in calibration; the duct-tape slate's corners are the remaining human step (checkerboard dives show the kernel works label-free, but a printed target is out of scope)** | E1c (dot-size calibration) **failed**: 84 % of dots clipped, so the width/range relation can't be pinned; **E1d focus distance failed** (the lens sits at infinity across the working range; hyperfocal 1.87 m), and **E1e flat-port depth is ruled out by calculation** (0.02–0.08 px at 1–3 m, 30–100× below what φ needs); mid-dive laser-state changes |
| **2. labels** | no human ceiling in prod (T1); labellers accept pre-fills 87 % of the time (T2); laser recall 0.821, with fixes to ~0.84 (T3); head/tail across domains (T4/T5); one labeller's landmark noise ≤0.6 % (T6) | **E2:** fully automatic length vs known length; **E3:** the human ceiling (T21) |
| supporting | frames per animal and range (T7), roll test (T8), TG-7 data exists | |

---

Eight tier-0 tests from `p2-tests.md`. T1/T2 ran on the 2026-09-25 nightly backup,
restored locally, and T3 ran on the production checkpoint over the NAS. The Lite half of
T5 and T9 are still waiting on a larger GPU. T3 would also benefit from the detector's
train/val split.

| test | where | pinned by |
|---|---|---|
| T1/T2 laser label pairs | `annotation_analysis/laser_label_pairs.ipynb` | `tests/test_laser_pairs.py` |
| T3 laser-detector recall | `laser_detection_analysis/recall.ipynb` | `tests/test_laser_detection.py` |
| T4 cross-domain head/tail | `annotation_analysis/headtail_cross_domain.ipynb` | `tests/test_headtail.py` |
| T5 fork decomposition (Mobile) | same notebook | `tests/test_headtail.py` |
| T6 landmark-noise bound | `annotation_analysis/landmark_noise_bound.ipynb` | `tests/test_landmark_and_field.py` |
| T7a/b frames per animal, range | `deployment_analysis/field_frames_and_range.ipynb` | `tests/test_landmark_and_field.py` |
| T8 roll test | `calibration_analysis/roll_test/README.md` | reproduction table in that README |

Code is in `fishsense_cscw/`. The frozen inputs and their provenance, including one
orphaned producer, are in `data/PROVENANCE.md`. `uv run pytest` runs 18 tests.

---

## T1 — there is no laser inter-annotator ceiling in prod

The 755 "doubly-labelled" images reproduce exactly on the current backup, but they are
not two opinions:

- **751 of 755 span two different Label Studio projects**, a median ~260 days apart.
  They are re-labelling campaigns, not two people on one task.
- **The later project was pre-annotated with the earlier human label.** Of 717 pairs with
  a dot on both sides:
  - **626 accepted the seed unchanged.** 450 of them are exact to float precision,
    including all 448 on mixed canvases.
  - **85 nudged it**, median under 1 px.
  - **Only 6 were drawn with no seed.** 4 of those disagree by 390–850 px, i.e. about
    *which* dot.
- **The seeds were human labels, not detector output.** They sit 0.0–0.4 px from the old
  human label and 1.2–1.4 px from the v2 prediction.

**`HANDOFF.md` §4.2 was right; `p2-inventory.md` §3.1 was wrong** (now corrected in
place). The laser ceiling has to be collected. It is cheap (a median 12.9 s per label),
so fold it into T21.

## T2 — replaced by a measured anchoring effect

- **Shown a seed, labellers accept it unchanged 87 % of the time** (626 of 711).
- **Seeds whose source is now superseded are still accepted 77 % of the time**, against
  94 % for live seeds. Labellers discriminate, but weakly.
- **A "moved" seed moves a median of under 1 px**, which does not fix a wrong dot.
- **184 images hold only accepted copies of a superseded label** and now have **no live
  laser label**.
- **No accepted seed was ever later corrected by more than 5 px.**

Consequences for P2:
- The detector's **"93 % byte-exact agreement"** (`auto_accept.py`) is an acceptance
  rate for this same interface, not an accuracy figure.
- **Detectors must be scored only against labels drawn without a seed.** T3 will do this.
- This is the observational baseline for the **T22** pre-annotation trial, which must
  measure anchoring as well as speed.

Caveats:
- "Superseded" is the line-fit validator's judgement (or a routine replacement), not
  ground truth.
- The data cannot say whether a seed was flagged before or after it was accepted.
- These seeds were prior *human* labels. Anchoring on *model* seeds is not measured here.

**A side number for T3:** where a v2 prediction exists on these images (n≈200), it lies
about 1.4 px from the old human label. That is promising, but it is provisional until
the detector's training split is known, because scoring on training images would
inflate it.

## T3 — laser-detector recall: 0.821, green missed 4× as often, pool hardest

Production checkpoint (sha256 verified) on 1,571 frames across 249 dives, scored against
**unseeded** human dots. The detector always returns a point, so "present" means
confidence ≥ 0.5, the threshold in its config.
`laser_detection_analysis/recall.ipynb`, pinned by `tests/test_laser_detection.py`.

| production (`wavelength=None`) | recall | missed | confidently wrong |
|---|---|---|---|
| **all** (1,221 dot frames, 226 dives) | **0.821** [0.80, 0.84] | 11.5 % | 6.4 % |
| red | 0.860 | 5.7 % | 8.3 % |
| **green** | **0.752** | **21.7 %** | 3.1 % |
| red, reef / pool | 0.940 / **0.736** | 2.0 / 12.6 % | 4.0 / 13.7 % |
| green, reef / pool | 0.790 / **0.426** (n=47) | 18.5 / 48.9 % | 2.5 / 8.5 % |

The false-alarm rate on the 350 no-dot frames is **11.1 %** [0.08, 0.15].

- **A missed dot is a lost measurement, and 11.5 % are missed.** Another 6.4 % get a
  confident wrong point, which is a bad measurement. Those sit at a median confidence of
  **1.000**, the same as correct points, so confidence says whether a dot is present but
  not whether the point is on it.
- **Green is missed about 4× as often as red.** The red-minus-green recall gap is
  +0.03 to +0.19 when resampling whole dives. P1's "green for reliable detection" is
  contradicted *for this detector*. That is about the model, not about optics.
- **Pool is the hard environment.** That reverses `auto_accept.py`'s "~93 % on pool, a
  reef problem". T2 explains the 93 %: it was an acceptance rate.
- **Production withholds the colour, and that costs green ~4 points** (0.752 vs 0.790
  when given). Red barely moves.
- **Compared with the checkpoint's own held-out validation** (`hit_n3 = 0.550`,
  presence recall red 0.979 / green 0.844), this sample is *harder*, not easier (presence
  rate red 0.943, green 0.783). That is the opposite of what training overlap would
  produce. It is not proof, and the train/val split is still wanted.
- **The docstring's `hit_n3 = 0.9081` is not the checkpoint's number.** See inventory
  §2.2.

**Can it be fixed? Tested on the same predictions** (`recall.ipynb`, last section):

| fix | cost | effect |
|---|---|---|
| lower the presence threshold | none | **not a fix**: 0.5 → 0.1 gains 1.8 pt recall, false alarms 11 → 28 %. Missed dots sit at confidence 0.05. |
| **1. pass the laser colour** | inference only; production already reads the colour off the dot after predicting | **+3.8 pt green, +2.2 overall.** 221 of 262 dives are single-colour. |
| **2. dive line as a corridor at inference** | inference only; the port has the corridor mode, production never passes a line | with ≤11 other dots per dive, a 25 px corridor rejects **54 % of wrong-spot dots and 84 % of false alarms**, flags 9.6 % of correct ones. A full dive's line (~3 px) should cut that cost. Must be *this* dive's line. |
| 3. retrain: wavelength-balanced, pool hard negatives | training repo (not on disk) + GPU | the only route to the missed green and pool dots; 46k unseeded dots now available |

Confident-wrong dots are mostly a **different bright spot** (57 of 78 are >100 px away,
median 592 px), at confidence 1.0. Together, fixes 1 + 2 give recall ~0.84, halve the
wrong-spot measurements and cut false alarms to ~2 % without touching the model.

**Runtime:** about 11 h, limited by the NAS link (~0.7 MB/s), in P4's environment with
`fishsense_core` 4.0.0 (production's pin) and torch overlaid for this run only.

## Hardware specificity — data already exists (found 2026-09-25)

The one barrier in `HANDOFF.md` §1 that no paper owns. **FSL-08 and later are TG-7s**
(the fleet's first four-plus units are TG-6s). Two TG-7s, FSL-10 and FSL-11, have a full
2025-01-17 San Diego session in prod:

| dive folder | images per unit | labels / measurements |
|---|---|---|
| Box (P1's rigid 150 mm target) | 8 / 26 | **none** |
| Session01 | 9 / 26 | none |
| LaserCalibration (checkerboard) | 28 / 32 | none |
| LensCalibration | 150 / 205 | intrinsics exist (cameras 9, 11) |

None of it was ever labelled or measured. It most likely stalled because the laser
calibration is a checkerboard, which the pipeline skips without error
(`fishsense-lite/docs/plans/checkerboard-laser-calibration.md` §0.5).

**Labelling the 34 Box frames (about 20 min) plus one checkerboard laser calibration gives
the first TG-7 accuracy number against a known length.** That is the cheapest route to
the barrier. P1's Table 2 already prices a TG-7 ("OM SYSTEM Tough 7", $549.99) while its
text describes a TG-6, so this backs a claim P1 half-makes.

## T4 — the detector across domains

All errors are % of the human snout–fork length, per frame, orientation resolved.

| | Mobile (in air) | Lite, Fishial | Lite, SAM3 |
|---|---|---|---|
| frames labelled / predicted | 151 / 148 | 167 / 90 | 167 / 117 |
| coverage | 98.0 % | 53.9 % | 70.1 % |
| snout p50 | **1.74 %** | 2.66 % | 1.52 % |
| fork p50 | **4.79 %** [2.56, 6.14] | **8.99 %** [6.35, 13.45]* | 8.37 % [5.21, 12.58]* |
| fork / snout | 2.75× | 3.39× | 5.51× |
| signed length error p50 | **+2.0 %** | +0.2 % | +0.4 % |
| usable (≤5 % length, of labelled) | 80.8 % | 31.1 % | 47.9 % |

\* Lite intervals resample whole dives (six of them).

- **Snout error is domain-invariant; fork error roughly doubles underwater.** The fork
  gap survives size-matching (Lite fork 9.7 % inside Mobile's size band), but that rests
  on only 12 frames from 3 dives.
- **The coverage gap cannot be credited to in-air vs underwater.** At the segmenter's
  input the median Mobile fish is 520 px against 125 px for Lite, about 4× larger. Lite
  coverage runs from 0 % below 75 px to about 70 % above 125 px. The fair comparison is
  Lite through the SAM3 1800×1350 laser crop, which rescales by 0.56 (Mobile: 0.55). That
  needs the NAS and a GPU.
- **Mobile reads 2 % long; Lite does not.** T5 explains part of it.

## T5 — the fork error is lateral, not a fixable offset (Mobile)

- The tail lands **0.8 % of length past the notch**, in 78 % of frames. That is
  systematic but small.
- The **typical error is sideways: 4.0 % of length off the body axis.**
- Subtracting a constant offset barely helps: 4.79 → 4.61 %.
- The mask reaches 3.5 % of length past the human fork and is about 19 % of length wide
  there. The spread caudal lobes are inside the mask, so the notch is a concavity between
  two convex tips, and the geometry step lands beside it.

**This answers `headtail-prediction.md` §9.2 for Mobile. The fix is a notch finder, not
a calibration constant.** The Lite half needs predicted coordinates, which the frozen run
did not keep. Underwater fins are often translucent, so the answer may differ.

## T6 — one labeller's landmark noise is at most ~0.6 % of length

- The bound is **0.56 %** (0.25 m bins, 39 cells, 6 dives), which is about **2 px per
  endpoint**. It stays at 0.56–0.75 % across every binning choice.
- **The handoff's estimator was corrected.** "Spread of the best-presented frames" is
  biased low. The upper half-width about the cell median errs high, which is what a bound
  needs.
- **This is intra-labeller consistency on rigid models**, not the inter-annotator
  ceiling (T2, T21).
- **The detector is far from one labeller's own consistency.** Its snout error is 2–4×
  the bound and its fork error about 10×.
- **Random noise cannot produce P1's near-range −6.8 % Weasly bias.** The one
  near-range cell spreads only about 0.24 %, so if the bias is a landmark effect it is
  systematic. That rests on one cell.

## T7 — what divers delivered, against what the estimator needs

P1 derives both requirements below from its own analysis. Nothing shows divers were told
either at collection time, so these are shortfalls, not non-compliance.

- **Frames per animal: median 2, max 8, none of 73 animals reach 10, and 42 % (31)
  have exactly one frame.** Every field p90 is a sample maximum, and for 31 animals it
  is a single photograph.
- **Range: 22 % of measured frames are inside 1 m**, the regime P1 advises against.
  One deployment (dive 341) is 74 % inside 1 m, which points to a per-diver or per-site
  habit.
- **P1's Table 1 advertises a 2–5 m working range, but only 27 % of field frames fall
  in it** (median 1.49 m, max 3.9 m). That is a discrepancy inside P1.

## T8 — roll test: not settled, and the "strong hint" does not survive

Full table and reproduction checks are in `calibration_analysis/roll_test/README.md`.

- **The same-session LEGO pair points to the sensor, not the board.** Sensor
  **0.9916** [0.9854, 0.9964], which matches P1's fleet value of 0.99141.
- **That flips with the choice of fixed distortion.** With the 2024 garage distortion,
  both terms are indistinguishable from 1.
- **The checkerboard pair points to the board**, but it is cross-session and internally
  inconsistent with the LEGO's sensor estimate.
- **The calipered board pitch pushes the wrong way.** That is not a code bug (the axis
  assignment was checked).
- **4 of 14 rolled LEGO views are mismatched by P4's matcher**, against 1 of 21 upright.
  Unscreened, they fabricate a strong board-side flip, and this analysis briefly
  reported one before the per-view screen caught it.
- **The P2 consequence:** "roll the camera", the obvious protocol line, currently yields
  bad correspondences 29 % of the time.
- **What settles it:** T18 (same-session horizontal board), a joint distortion fit, and
  more rolled views. None of this reaches delivered length, where P4 §5 puts the whole
  anisotropy at 0.137 pp.

---

## Corrections these results make to earlier documents

- **`p2-inventory.md` §3.1, status row 3, §7B.1 and §10:** "the laser ceiling is
  collectable today from 755 pairs" is wrong (T1). Corrected in place with a banner; the
  original text is kept.

- **`p2-inventory.md` §1.3:** "fork ~1.9× snout on Mobile" is a ratio of *pixel*
  medians. Per frame, in % of length, it is **2.75×**. Fixed in place.
- **`HANDOFF.md` §5 item 1:** the estimator as described biases low (T6 above).
- **`roll-test-for-camera-ready.md` (P4):**
  - the "strong hint" is contradicted by the clean pair (T8);
  - the vertical solves do not time out, they were fed four broken views;
  - its value is reproduced only with same-session distortion.

## For the other papers' authors (adds to `p2-inventory.md` §7D)

- **fishsense-lite:** re-population seeds new laser projects with the previous human
  label, and 184 images now have no live laser label as a result (T2). Also, the
  "93 % agreement" in `auto_accept.py` should not be read as accuracy.

- **P1 Table 1's 2–5 m range** does not describe the field corpus (T7).
- **`auto_accept.py`'s "reef problem"** is a single unlabelled dive. On unseeded labels
  the reef is where the detector does best (red 0.940), and the pool is worst (T3).
- **P1's green-laser rationale:** the production detector misses green 21.7 % of the
  time against 5.7 % for red (T3).
- **P1 Table 2 prices a TG-7** ("OM SYSTEM Tough 7") while the text describes a TG-6.
  The fleet has both. The TG-7 has no accuracy result yet, but the data for one exists.
- **P4's Limitations say a rolled recapture "would settle it."** One was taken, and it
  does not settle it without a joint distortion fit and a same-session board pair (T8).
