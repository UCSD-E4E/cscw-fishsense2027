# P2 test plan — 2026-09-22

## Scope, set 2026-09-26 (supersedes the framing below where they differ)

**P2 is about how to do citizen science with FishSense Lite, with end-to-end automatic fish
measurement from still images as the goal.** Stills only; video is a future paper (see E1j).
The paper analyses:

1. **The detectors:**
   - laser dot (T3, T3b);
   - fish (Fishial vs SAM3; T9 and the inventory's backend table);
   - head/tail keypoints (the headtail cross-domain work).
2. **The calibration methods:**
   - intrinsics: **LEGO stays** for now (P4). SfM is deferred to the video paper.
   - laser: slate with automated corners (E1a); unknown-size rigid object, label-free
     (E1j); |O| from the mount CAD.
   - the negative results that motivate those choices (E1c–E1i, E1k).
3. **The end-to-end pipeline:** dot → fish → head/tail → calibrated length, with no human
   step, scored against known lengths (E2).

## Restructured 2026-09-25: two pillars, three core experiments

P2 removes two sources of friction: **(1) the per-dive calibration** and **(2) the human
labels.** REEF left over the first (see `p2-results.md`). The core experiments:

### E1 — Label-free calibration on real dives *(pillar 1; existing data, no GPU; in progress)*

Can a dive be calibrated with nobody labelling anything? Two routes, both validated on
P1's pool dives against known lengths, which are only ever used as the check:

- **E1a, keep the slate photos, drop the labels.** Laser dots from the detector (T3),
  slate corners from the gated slate predictor (`2026-07-31_slate_training`: 80 % of
  frames seeded, 5.9 px median). Same stage-13 fit.
- **E1b, drop the slate.** Scale-free self-calibration from the dive's own rigid objects
  (`scalefree_laser_selfcal.ipynb`). This works on the Box (0.003°) and fails on solid
  fish models. Wild fish are unlikely to qualify (T7: median 2 frames per animal, and
  they flex).
- **Also: mid-dive laser-state changes.** P1 documents three states in one dive. The
  dive line jumps when the mount moves, so calibration must be per segment.

**Success:** measured lengths from the label-free calibration match those from the
labelled one within the error budget, reported as coverage (dives calibrated) and accuracy.

### E1c — Calibrate from the laser dot's own size *(pillar 1)* — **FAILED all three pre-registered checks, 2026-09-25**

> 701 dots, 24 dives, zero read errors (`calibration_analysis/e1c_dot_size/score.py`).
> 1. **Physics:** median residual 0.38 px (minor axis 0.34); 7 of 8 dives over the 0.3 px
>    kill line, none under 0.1.
> 2. **Constancy:** c ranges −0.85 to +1.62 px across cameras, negative on half, so
>    unphysical.
> 3. **Blind:** 0 of 2 within 0.05°; off by 0.6–1.2°.
>
> **The cause is exposure, not geometry:** 84 % of dots are clipped, 98–100 % below
> 1.5 m. The usable dots sit at 1.5–4.4 m, with too little 1/Z spread to pin the line.
> The geometry itself is untested on unclipped dots. A dimmer laser or an ND film could
> revisit it, but that is a hardware change.
>
> **Checked on the raw mosaic, 2026-09-25** (`calibration_analysis/e1c_dot_size/raw_saturation_check.jsonl`).
> The clipping above was measured after `LinearRawImage`'s decode, which applies the camera
> white balance (red gain **~2.6×**) and caps at 65535, so it could have been a decode
> artifact. On 20 dots against the sensor's 4095 white level:
> - **The sensor really saturates** on all 10 dots at 0.28–1.39 m, 3 of 6 at 1.5–2.5 m,
>   and 1 of 4 beyond 2.5 m.
> - **White balance roughly doubles the clipped footprint**, and 2 mid-range dots that
>   E1c called clipped were not saturated on the sensor.
>
> A mosaic-based fit would recover some wing pixels and a few mid-range dots, but not the
> near-range leverage. **The verdict stands: exposure, a hardware limit.**

### E1d — Range from the camera's focus position *(pillar 1)* — **FAILED, 2026-09-25**

> The Olympus MakerNote records `FocusStepCount` (the lens position), `FocusStepInfinity`
> and `FocusStepNear` (9719 to 9810, just **91 steps** of travel), and `FocusDistance`.
> Tested in air on the 52 roll-test views, with true distance from each view's board pose:
>
> - **Checkerboard at 0.78–1.48 m sits at −5 to +2 steps from infinity.** Across the
>   working range the lens is at infinity, because the TG-6's hyperfocal distance is 1.87 m.
> - Step count correlates with 1/Z at only **+0.16**. 1–3 m falls inside about one
>   step, since 91 steps span infinity to macro.
> - **`FocusDistance` is a median 19× the true distance** (30 m to ∞ for a board at ~1 m).
>
> So autofocus carries no range information where divers shoot. This is a property of a
> small-sensor wide-angle lens, not of the analysis. Underwater would be the same or worse.


The dot is a "rigid object of unknown size" every frame carries. Its image width and its
position along the dive line are both affine in 1/Z:

  s = c + b/Z  (c = f·θ, the beam's divergence; b = f·D₀, its exit size)
  p = v + a/Z  (v is the beam's vanishing point, which carries φ)
  ⇒ **s = c + (b/a)(p − v)**, one equation per frame, with no D₀, no Z and nothing in the scene.

**The one degeneracy:** v and c trade off in the intercept. The system closes if c is
known, and c is a property of the *laser*, not the mount, so one in-air measurement or
spec-sheet value per laser suffices (divide by 1.33 underwater). Metric scale comes from
|O|, measured once per mount with a ruler.

**Run:** 701 frames, 25 of P1's pool dives, depth-stratified, median depth span 8.9×,
almost all red. Elliptical Gaussian on the 16-bit linear raw, fitted to *unsaturated*
pixels only (`calibration_analysis/e1c_dot_size/`).

**Pre-registered pass/fail, set before the data:**
1. **Physics:** within a dive, width against 1/Z (Z from the stored calibration) is
   linear with a residual of about 0.1 px or better, on dots beyond 0.8 m with little
   saturation. Worse than about 0.3 px kills the method: 0.1 px of width bias is about
   8 px of v, about 0.15°, about 4.5 % of length at 2 m.
2. **Constancy:** c is consistent across dives of the same laser.
3. **Blind:** with c from the *other* dives, v from dots alone recovers φ within 0.05°
   of the anchor calibration, and the known-length error stays inside the budget.

**Known risk, seen in the smoke test:** at 0.28 m, 890 of 1,681 patch pixels are
saturated (a ~33 px clipped blob); at 5 m, σ ≈ 1.5–1.8 px with one saturated pixel.
Brightness scales roughly as 1/Z², so bloom biases width in the same direction as 1/Z.
That is the failure mode to watch.

### E1e — Depth from the flat port's own refraction *(pillar 1)* — **ruled out by calculation, 2026-09-25**

> After P4 the camera is a weak axial camera, and an axial camera's image positions
> depend on depth. Measured with P4's exact port model (`calibration_analysis/e1e_flat_port_depth.py`):
> the depth signature in a laser dot's image position, after the best pinhole+radial fit,
> is **0.02–0.08 px across 1–3 m** at P4's standoff (d0* = 0.74 mm), against 2.5 px for
> 0.05° of φ and 1–3 px of dot noise. 30–100× too small. The whole 0.5–5 m range gives
> 0.44 px, almost all of it below 1 m, where dots clip and P1 says not to measure.
>
> To make it usable the camera would need to sit ~50 mm behind the pane (signature
> 3.7 px over 1–3 m), but that is the same standoff at which Pinax's depth-independent
> correction stops holding. **One dial, two ends: the standoff that lets you calibrate
> in air is the standoff that hides depth.** A deliberately deep port is a different
> instrument, not a fix for this one.

### E1f — Range from the dot's brightness *(pillar 1; pre-registered 2026-09-25, before data)*

Why it matters: REEF left over the laser's calibration. If the laser can calibrate
itself, FishSense is competitive again.

Physics: S ∝ P·ρ·e^(−2cZ)/Z² × exposure. Brightness depends on Z in a way that is **not**
affine in 1/Z, so combined with dot position and size it would break E1c's intercept
degeneracy in principle. The risks are unknown reflectance ρ per surface, clipping, water
attenuation c per dive, and auto-exposure per frame (recoverable from EXIF).

**Best-case test:** the 87 E1c dots that are not clipped, mostly on the white Box.
Brightness is summed from the raw mosaic's red photosites, black-subtracted and
background-subtracted, before white balance (the camera sets it per frame), then
normalized by t·ISO/N² from EXIF. Fit log S = k − 2 log Z − 2cZ per dive and target, with
Z from the stored calibration.

**Pass/fail, fixed now:** per-dot range error implied by the residual
- **≤ 5 %: pass**, usable on typical dives (~30 dots pin v to ~2.5 px)
- **5–15 %: marginal**, usable only on dives with many frames
- **> 15 %: fail**
Also report c per dive; it should be physically plausible, 0.05–1 m⁻¹ for red.

If the best case (a white box) fails, dots on fish will not pass either.

> **Result, 2026-09-25 (`calibration_analysis/e1f_intensity/`): FAIL as pre-registered, but underpowered.**
> 110 unclipped dots were read from the raw mosaic, with exposure normalized from EXIF.
> - **Only 2 dive × target cells qualified** (≥5 dots over ≥1.3× range). Dive 61
>   angelfish came in at 8.2 % (marginal), dive 76 shark at 65 %, and both fitted
>   attenuation *negative* (unphysical; too few dots over 1.7–2.5 m to pin c).
> - **With c fixed at the pooled, plausible 0.22 m⁻¹**, the median across 17 cells is
>   **8.7 %**, with the best cells at 1–7 %. That is optimistic, since the cells have
>   3–8 dots each.
> - **The white Box did worst** (11 %, 23 %), because its unclipped dots are all dim and far
>   (2.7–4.3 m).
>
> **The same root cause as E1c:** the dot saturates wherever divers actually shoot. The
> existing data cannot decide it. → E1g.

### E1g — Dimmed-laser capture: test size and brightness on unclipped dots *(pillar 1; WITHDRAWN 2026-09-26)*

> **Withdrawn.** This design dims the laser with ND film, and real-water range needs the full
> beam, so the film is rejected. E1h shows the undimmed dot's size and brightness can't be read
> in software either. The simulation below still holds, but only for a dimmed beam.

One pool session with the laser dimmed (an ND film over the pointer, or a lower-power
pointer), and normal camera settings. Shoot the white Box and two fish models stepped from
0.5 to 4 m, with the slate in a few frames as ground truth. Then test E1c (size) and E1f
(brightness) on unclipped dots across the full working range, plus the combined fit:
position, size and brightness together, which breaks E1c's intercept degeneracy in
principle. **If it passes, the laser calibrates itself from every dive's own dots**,
removing the calibration step REEF left over, with a commodity change rather than a
fabricated target.

**Shot list (about 1 hour in the pool):**

*Camera:* one TG-6 unit on its usual mount, raw (ORF) capture, **ISO locked at max** (the
recommended deployment setting). Shutter and aperture stay on auto, as deployed, and
EXIF records them. The existing pool corpus is ISO 1600 and 100 only, so this is also
the first laser test at the recommended setting.

*Laser:* red first; green as a second pass if there is time (T3: green is the weak
wavelength). Bring ND gel or film for the pointer in **2, 3 and 4 stops**
(ND 0.6 / 0.9 / 1.2). Brightness spans about 64× from 0.5 to 4 m, and near dots
currently clip hard.

1. **ND ladder, about 5 min.** White Box at 0.5 m and at 4 m, 2 frames each, with no ND
   and each ND strength (16 frames). The ND is chosen in analysis rather than by eye:
   the weakest one that leaves the 0.5 m dot unclipped while the 4 m dot is still
   detectable.
2. **Slate burst A, start of session.** 10 frames at spread ranges (at least 1 m apart
   end to end), dot on the slate. This is the ground-truth φ.
3. **Range steps, with the chosen ND fitted and the mount untouched from here on.**
   Distances 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0 m. At each, 5 frames on each of:
   - white Box (flat, constant reflectance: the best case)
   - Rainbow Trout and Snook (round and textured: the realistic case)
   - pool wall or floor, 2 frames (flat and uniform: clean brightness data)
   Mostly broadside, some up to ±15°, dot on the target. About 140 frames.
4. **Slate burst B, end of session.** Same as A. It checks the mount held (P1: bursts
   at two times are the only direct evidence of that).
5. **Optional, if time allows:** repeat step 3 with no ND, at 1, 2 and 3 m only. That's
   the baseline for how much the ND buys.

**What it decides:** E1c (size) and E1f (brightness) on unclipped dots across the full
range, then the combined position + size + brightness fit, scored blind against slate
bursts A and B. Box and fish lengths are the known-length check. The pass/fail criteria
are E1c's and E1f's, unchanged.

**Why the combined fit is the one to bet on** (`calibration_analysis/e1g_simulation.py`).
Per dive the only unknown is φ, and a dive has hundreds of dots, so a cue must be
*unbiased*, not precise per dot. Each cue has exactly one nuisance constant that trades
off against φ:
- **size:** the beam divergence, a *laser* property, measured once and stable
- **brightness:** the water absorption, which changes per dive

Brightness has no additive constant, because total power does not grow with range, so
√S is linear in dot position and crosses zero at the vanishing point. Fitting absorption
jointly does *not* work (0.27–0.8°). Size with a once-measured divergence does. In
simulation, with 300 dots over 0.5–4 m and 0.2–0.3 px width noise (E1c's clean dives
already show 0.18–0.33 px):
- size alone reaches 0.023–0.035° if divergence is exact, and ~0.08° if it is 0.05 px off
- **size + brightness reaches 0.040–0.045° with divergence 0.05 px off and absorption
  30 % off.** The two biases partly cancel.

**Add to the session:**
6. **Laser constants, in air, inside the LEGO session (about 10 min).** Photograph the
   dot on the LEGO target at 1–5 m, 3 frames per distance, with the chosen ND. The LEGO
   pose gives each dot's true distance, so width against 1/Z yields both **beam
   divergence** (the intercept, needed to about 0.05 px; scale by 1/1.33 for water) and
   **beam exit size** (the slope). These are properties of the *laser*, not the mount:
   measure once per pointer. (A flat wall at taped-off distances works if the LEGO
   session isn't available.)

**The split this implies for deployment:** one in-air LEGO session per camera and laser
gives intrinsics (P4), the mount offset |O|, a starting φ, divergence and exit size.
**Each dive then re-estimates φ from its own dots**, and in principle |O| too, since the
size slope is exit size ÷ |O|. There's no slate and no diver action. Mid-dive mount shifts
are tracked only at the rate dots accumulate (~100–300 per estimate).
7. **Detector recall on dimmed dots.** Run the T3 detector on the step-3 frames. A dimmer
   laser must not cost detection (T3's detector was trained on bright dots).

**Risks the simulation cannot see:** the brightness law must hold on real dots (E1f's fell
off slower than 1/Z², unexplained), so the physics checks come first. And field dives
span a narrower range than 0.5–4 m.

### E1h — Read size and brightness off the *undimmed*, clipped dot *(pillar 1)* — **FAILED, 2026-09-26**

> Dimming the laser is ruled out, because it costs range in real water. Two software routes were tried.
>
> **1. The Bayer mosaic as a built-in ND filter** (`e1c_dot_size/bayer_channels_check.jsonl`, 20 dots).
> Green photosites clip almost as often as red (11/20 vs 13/20). Blue clips on 5/20, all at
> ≤0.8 m, so it rescues dots at ~1–1.8 m but not the near range that carries the leverage.
> (The flux ratios in that file are scene-contaminated and meaningless.)
>
> **2. Fit the clipped spot's unclipped wings** (`e1h_clipped_wings/`, 90 dots, dives 501/504/506,
> 0.28–4.97 m). Fits log I = log A − r²/2σ² on raw red and blue photosites:
> - **Not Gaussian:** on clipped dots the fitted peak is 0.30 of full scale (red) and 0.15
>   (blue); it must exceed 1.
> - **Width residual 4.5–36 px** within a dive (target 0.1).
> - **Brightness slope +0.1 to +0.4 against log Z** (inverse square predicts −2).
> - **Near and far dots sit 70–320 px off one line.**
>
> The wings are a halo (water scatter, blooming, flare), not the beam profile.
>
> **Conclusion:** at deployed exposure, an undimmed dot's size and brightness cannot be
> read. Dot-based self-calibration (E1c/E1f/E1g) requires dimming, which is rejected, so
> that route is closed. Next candidate: a second laser in the same printed block, whose dot
> *separation* gives range from dot centres, which clipping does not disturb.

### E1i — Light loss from the undimmed dot's aperture-summed brightness *(pillar 1)* — **FAILED, 2026-09-26**

> The same 90 dots as E1h (dives 501/504/506). This time the brightness is a wide-aperture sum
> of (I − ring background) per Bayer channel on the raw mosaic, normalised by t·ISO/N² from
> EXIF, so halo light is counted rather than fitted. Only dots with no clipped photosite in
> the aperture are used. The fit per dive × target is log S = k − 2 log Z − 2cZ (as in E1f).
> Code: `calibration_analysis/e1i_aperture/`.
>
> **Red and green, 45 px aperture:**
> - Unclipped only beyond ~2.5–3 m (12 and 19 dots).
> - Free slopes −1.3 to −2.4, close to inverse square.
> - Per-dot range error 12–19%, against a 5% bar.
> - Fitted absorption c ≤ 0, which is unphysical.
>
> **Blue:**
> - Unclipped from 0.7 m, but brightness *rises* with range (slopes +1.1 to +1.9 on 2 of 3 dives).
> - The sum is dominated by the target's own blue light, not by laser light.
>
> **Conclusion:** light loss is a weak range cue, at 12–19% per dot, and only in the far band
> where φ leverage per dot is lowest. It cannot calibrate φ on its own, and on the evidence
> so far it cannot be combined with size either (E1h).
>
> **These numbers are the best case.** Each fit holds one target, so reflectance is constant
> within it. A field dive mixes species, materials and incidence angles, and reflectance then
> varies per dot, which absolute brightness cannot separate from range. Across these data the
> intercept k differs by about 1 log unit between targets (≈2.7× reflectance). Taken as range,
> that is an error of tens of percent per dot.
>
> **Full run, 2026-09-26: all 700 red-laser frames with raw files, 24 dives, 7 target
> types.** Cells are dive × target with ≥5 unclipped dots over a ≥1.3× range.
>
> | channel, aperture | cells | per-dot range error, median | cells ≤5% | slope vs log Z, median (IQR) | slope > 0 | c physical (0.05–1) |
> |---|---|---|---|---|---|---|
> | R, 20 px | 11 | 17% | 1 | −1.44 (−2.81…−0.75) | 9% | 36% |
> | R, 45 px | 11 | 32% | 1 | +0.14 (−1.05…+0.77) | 55% | 9% |
> | G, 45 px | 22 | 16% | 1 | +1.74 (+0.82…+2.70) | 77% | 5% |
> | B, 45 px | 27 | 27% | 0 | +1.91 (+1.10…+3.28) | 81% | 4% |
>
> - **Repeat shots of one target scatter** by a log SD of 0.5–0.75 (×1.6–2.1). That is dot
>   placement and incidence angle on the model.
> - **Mixed dives** (7 red, 9 green): between-target reflectance spread median ×2 (max ×8).
> - **A per-target reflectance barely helps:** 30% vs 34% (red) and 31% vs 33% (green), because
>   the within-target scatter dominates.
> - **Green and blue get brighter with range** in about 80% of cells. At those photosites the
>   target's own light, not the laser's, dominates the sum.
> - **Only red in a tight aperture** is roughly physical (median slope −1.4), and it is still
>   17% per dot.
>
> **Verdict:** light loss from the dot is not a usable range cue at full power, even with
> reflectance known per target.

### E1j — Size constancy: the same object measured at several ranges fixes φ *(pillar 1)* — **PROMISING (pool), 2026-09-26**

> **Credit, corrected 2026-10-07 (author).** Size constancy, its label-free variant and the
> slate-frame detector are this paper's contributions, not WUWNet's. WUWNet covers in-air lens
> calibration (LEGO, Pinax). The sections in `wuwnet-fishsense2026/correspondence/p2/
> LASER_SECTIONS_FOR_P2.md` (2026-09-19) were prepared for this paper, and E1b above
> (`scalefree_laser_selfcal.ipynb`) is its earlier form here. That document has the locus geometry, a decoy
> end-to-end test (+0.0% median on a held-out board, −0.4% absolute scale), the production
> cross-check (Box 0.003°), the thickness failure mode, and the rule that size must be
> measured on the dot's surface without range drift (√mask area best). E1j re-derived it.
> E1j's own contributions are the label-free registration variant on 10 slate sessions and the
> E2 tape-length cost.

> **Why the dot alone and a second laser both fall short.** With the offsets |O_i| known (ruler)
> and the angles unknown, the dot positions p_i = v_i + A_i/Z allow v_i → v_i + A_i·ε for any ε,
> i.e. 1/Z → 1/Z − ε. The shift is the same for every laser, so a second laser with an unknown
> angle between the beams leaves the same one-parameter ambiguity (a common-depth assumption
> fixes only v1 − (A1/A2)·v2). A second laser helps only if that angle is calibrated in air,
> and PLA creep can move it.
>
> **What breaks it.** An object of fixed but unknown length, measured at several ranges: its
> length L_k = ℓ_k/(f·(1/Z_k − ε)) is constant only for the true ε. That needs no target, no
> in-air angles and no second laser, only |O| from a ruler and head/tail points.
>
> **Pool check.** 43 dive × target cells, from the stored human head/tail lengths
> (`frames.csv` length_m) and stored depths. Fit ε to minimise the variance of log L, then
> read it as φ relative to the slate calibration, with a 200× bootstrap SE.
> - **All cells:** |Δφ| median 0.097°, SE median 0.044°; 14/43 within 0.05° and 32/43 within 0.15°.
> - **Wide-range dives (491–527, 13–30 frames, 0.3–5 m):** SE 0.010–0.036°, and |Δφ| mostly
>   ≤0.1°. Trout dives lean −0.06° to −0.1°, and it is unclear whether that bias is the
>   method's or the slate calibration's.
> - **Narrow-range old dives (58–84):** SE 0.02–1.2°.
>
> **Caveats.** These are rigid models, posed broadside. Real fish bend and turn away, and
> foreshortening only ever *shortens* the apparent length, a one-sided bias. The method also
> needs the same fish identified across frames.
>
> **Next steps:**
> - Use the models' known physical lengths to separate method error from slate-calibration error.
> - Measure how often field dives photograph the same fish at ≥1.5× range spread.

> **Field check, 2026-09-26: the corpus cannot test it** (`e1j_size_constancy/field_bursts.py`).
> Same-fish groups come from time bursts (5/30/120 s) or from the DB's `diveframecluster`,
> which holds 2,996 predicted clusters (5,059 frames with head/tail + dot) and 3,034 human ones.
> - The within-group range ratio has a median of **1.01–1.06**: divers shoot a fish in a burst
>   at one range, and the clusters are near-duplicates.
> - The fitted φ SE has a median of 0.18–0.33°, and 0–7 dives reach 0.05°.
> - A field test needs frames of the same fish at ≥1.5× range spread, e.g. shot while
>   approaching it. That would be a protocol change, not a data problem.

> **Slate as an object of UNKNOWN size, 2026-09-26: PASSES wherever the range spread is ≥1.5×**
> (`e1j_size_constancy/slate_unknown.py`).
> - **Size measure:** the RMS radius of the 8 labelled slate points, which goes as 1/Z.
> - **Fit:** t_v minimising var(log(s/(t − t_v))). The slate's physical size is never used.
> - **Reference:** the stored calibration's laser axis, projected onto the dive line.
>
> | dives | size spread | |Δφ| vs stored cal | within 0.05° |
> |---|---|---|---|
> | 10 (slate sessions 62–83, angle tests 87/94/114) | 1.75–2.9× | median **0.016°**, max 0.060° | 9/10 |
> | 107, 22, 103, 526 | 1.01–1.12× | unconstrained (SE 10–25°) | — |
>
> - Bootstrap SE is 0.6–2.3 px (0.012–0.046°), and 9/11 errors fall within 2 SE.
> - **Caveats.** The stored calibration came from these same frames via known-size PnP, so
>   this shows the *size itself* is unnecessary, not that the result is independent of those
>   labels. These are dedicated Aug 2023 slate/angle sessions, not ordinary field dives.
> - **Consequence.** Any rigid object of unknown size, shot at a ≥1.5× range spread with the
>   dot on it, calibrates the laser to the 0.05° target. The known template and known size
>   are not needed.
> - **Next.** Make it label-free: the scale ratio between frames of the same object is
>   measurable by image registration (local homography scale at the dot), with no corner
>   labels.

> **Label-free and template-free, 2026-09-26: PASSES** (`e1j_size_constancy/register.py`).
> - **Features:** SIFT within 700 px of the dot on half-size raw decodes (258 frames, 10 dives).
> - **Pair scales:** every frame pair gets a RANSAC similarity. Of up to 3 motion layers, the
>   object's is the one with the most inliers within 80 px of the dot, because the dot is on
>   the object.
> - **Per-frame size:** log s_k comes from a weighted least-squares solve over all pairs. Pairs
>   beyond 4 robust SDs are dropped (SD floored at 1% of scale).
> - **Fit:** the same size-constancy fit as before, against the stored calibration.
>
> | dive | frames | size spread | error | SE |
> |---|---|---|---|---|
> | 62 | 20 | 1.75× | +0.033° | 0.049° |
> | 63 | 12 | 2.15× | −0.002° | 0.071° |
> | 65 | 27 | 2.92× | +0.025° | 0.013° |
> | 71 | 32 | 2.90× | +0.009° | 0.020° |
> | 77 | 22 | 2.46× | +0.009° | 0.020° |
> | 80 | 31 | 2.72× | +0.007° | 0.023° |
> | 83 | 26 | 2.21× | −0.038° | 0.028° |
> | 87 (angle test) | 30 | 2.21× | −0.031° | 0.011° |
> | 94 (angle test) | 21 | 2.06× | −0.044° | 0.018° |
> | 114 (angle test) | 29 | 2.18× | −0.129° | 0.089° |
>
> - **9/10 within 0.05°, 10/10 within 0.15°,** median |error| ≈ 0.02°. The registration scale
>   correlates 0.98–1.00 with the labelled slate size.
> - **What it took to get there:**
>   - layer selection near the dot, since otherwise the static pool background or moving
>     people win (87/94/114 read 1.0× at first);
>   - a neighbourhood on the object's scale (80 px, not 250);
>   - dropping zero-weight pairs.
>
>   A homography model was worse than a similarity on face-on slates.
> - **Caveats:**
>   - The reference is the known-size slate calibration from the same frames.
>   - These are pool sessions with a textured slate filling part of the frame. Field
>     objects (rock, dive light) are untested.
>   - The 80 px neighbourhood suits this slate at these ranges. It should scale with the
>     object, e.g. from the matched layer's extent.

> **Video: OUT OF SCOPE for P2 (user decision, 2026-09-26); future "video" paper.**
> P2 stays a still-image paper; switching would redo too much existing work. Logged for later:
> - **Why video suits size constancy:**
>   - An approach clip gives the range spread for free.
>   - Frame-to-frame tracking replaces wide-baseline matching, so the dot-selected segment
>     carries through the clip and needs no fixed neighbourhood.
>   - About 150 frames per 5 s approach.
>   - Tracked real fish become calibration objects; bent frames can be dropped.
>   - Calibration is possible anywhere in the dive, so mid-dive drift is visible.
> - **Risks to test:**
>   - Electronic stabilisation must be off.
>   - Video-mode intrinsics differ (crop or scale), so each mode needs its own lens calibration.
>   - Compression and 4:2:0 chroma blur the dot's position.
>   - Rolling shutter and motion blur.
>   - Lower resolution than 12 MP stills.
> - **Hybrid:** calibrate from a short approach video, measure from stills. The laser tilt
>   is physical, so it transfers once each mode's lens mapping is known.
> - **First test:** a pool session with approach clips of the slate and a fish model
>   (stabilisation off) plus stills. Check `REEF/data/2024-12-13 Grouper Moon Videos` for
>   existing laser-on footage.

> **Metric scale from the mount's design, 2026-09-26.** Length scales as |O|, the lateral
> lens-to-laser offset, so a 1 mm error costs 1% (budget: 0.05° ≈ 1.5% at 2 m).
> - **Today's per-dive slate estimate of |O| is noisy.** Across 31 stored calibrations the
>   median is 104.0 mm. On one mount it varies between dives (101.0–104.9 mm on camera 2,
>   98.7–105.0 on camera 4), so it is roughly ±1.5 mm of estimation noise. One outright
>   failure: 129.5 mm on camera 5.
> - **Decision (user, 2026-09-26):** take |O| from the mount model (CAD), once per design.
>   It needs no ruler and no per-dive fit, and PLA creep mainly tilts the laser, which the
>   unknown-size fit re-measures every dive. Still to do: confirm the CAD value against the
>   104.0 mm fleet median.

### E1k — The laser beam's visible streak *(pillar 1)* — **red: signal but no precision; green: strong, testing, 2026-09-26**

> **Physics.** Water scatters the beam into a faint cylinder from the laser to the dot. Its
> image is a wedge: width grows linearly with distance from the beam's vanishing point v
> (both the physical width w/O and defocus scale as 1/Z). The apex gives v, i.e. φ, with no
> target, no brightness model and no clipping, because the streak is faint.
>
> **Probe** (`calibration_analysis/e1k_beam_streak/`: `probe.py`, `sides.py`, `wedge.py`).
> Transverse raw-mosaic profiles are sampled across the dot line and stacked over frames.
> A beam lies only on the laser side of each dot; an artefact aligned with the line would
> sit on both sides. Controls are lines 250 px to either side.
>
> | dive | laser | laser side (e-3 of full) | v side | controls |
> |---|---|---|---|---|
> | 257 Alligator Deep | red | +0.78 ± 0.08 | −0.30 ± 0.21 | ≈0 |
> | 318 South Ledge | red | +0.91 ± 0.17 | −0.20 ± 0.43 | ≈0 |
> | 331 Fire Coral Cave | red | +0.48 ± 0.31 | −0.32 ± 0.56 | +1.08, +0.07 |
> | 526 pool, evening | red | −0.63 ± 0.13 | +3.58 ± 0.51 | ≈0 |
> | 440 Alligator Deep 2024 | **green** | **+22.3 ± 2.2** | −1.4 ± 1.2 | ≈0 |
> | 475 Alligator Deep 2024 | **green** | **+14.0 ± 1.1** | +2.2 ± 1.4 | ≈0 |
>
> **Red, full dives (185 and 415 frames):** the wedge is visible (σ 3 → 9 px along the line),
> but the apex bootstrap SE is 205 px (4.1°) and 1441 px (29°), against a 2.5 px target. Dead.
>
> **Green** is 15–30× stronger (≈2% of full scale). Green scatters more, is absorbed less,
> and sits on the densest Bayer channel. It is also one-sided and widens (FWHM 4 → 16–18 px).
> **Green, dive 475 (230 frames): a clean streak, but it does not pin v.**
> - **Width** grows smoothly, σ 2.2 → 10.5 px, but the beam's divergence adds a constant.
>   So W = c_div + k(x − v), the same intercept degeneracy as E1c (k = 0.0074, so 0.02 px of
>   c_div is 2.5 px of v). Apex SE 47 px (0.95°).
> - **Integrated brightness** per pixel of line has no reflectance and no inverse square.
>   Model: ln I = k − 2cA/(x − v). It rises from 97 to 160 (e-3·px) over the first ~500 px,
>   then plateaus, which implies c ≈ 0.4 m⁻¹, plausible for green. The curvature trades off
>   against v: SE 126 px (2.5°), and half the bootstraps pin at the far dot.
> - **Verdict:** a real signal, 20–50× short of 0.05° per dive. √N over every laser-on frame
>   (~10×) still leaves ~0.3°. Usable only as a coarse drift or sanity check on the slate
>   calibration (≥1° errors), not as a calibration.
>
> **Green survey, all 7 dives, whole dives** (`truth.py`, `glow.py`, `wedge.py`). The streak
> is laser-side excess on the green photosites, in e-3 of full scale.
>
> | dive | frames | laser side | v side | slate cal? |
> |---|---|---|---|---|
> | 440 Alligator Deep, Oct 2024 | 300 | **+17.1 ± 0.7** | −0.8 ± 0.4 | no |
> | 475 Alligator Deep, Dec 2024 | 230 | **+21.8 ± 0.7** | −4.6 ± 1.5 | no |
> | 347 Alligator 0, Mar 2024 | 177 | +0.8 ± 0.9 | +1.4 ± 1.8 | yes |
> | 349 Alligator 0, Mar 2024 | 125 | +0.7 ± 0.7 | −0.6 ± 1.7 | yes |
> | 436 Alligator 0, Oct 2024 | 88 | −0.5 ± 0.5 | +1.7 ± 1.0 | yes |
> | 465 Alligator 2, Dec 2024 | 65 | +0.8 ± 0.5 | −1.5 ± 1.6 | yes |
> | 471 Alligator 2, Dec 2024 | 45 | +1.8 ± 0.9 | −0.4 ± 2.5 | yes |
>
> - **The streak appears on 2 of 7 green dives,** both the deep site, and on none of the five
>   calibrated ones. Without a streak, the apex fits are noise (SE 20–42°), so accuracy
>   against the slate could not be scored.
> - **Dive 440 brightness fit:** SE 43 px (0.86°).
> - **Verdict:** water-dependent, precise to about 1° at best where present. Not a
>   calibration, and not a dependable per-dive check either. It could flag gross drift on
>   deep or turbid dives only.

### E3s — Automatic species ID: BioCLIP 2.5 zero-shot on FishSense frames *(2026-09-28)*

> **Setup** (`e2e_measurement/species/`: `extract.py`, `classify.py`)
> - Classifier from `coral-gardeners-fish-detector` (UCSD CSE 237D class project; cite it),
>   run unchanged: `bioclip-2.5-vith14`, 4 prompt templates, closed 13-species `little_cayman`
>   REEF list, offline.
> - Truth: human `specieslabel` on 557 real-fish frames with a dot (482 had crops: 387 target
>   species, 95 "Other"), covering 39 dive × species groups. Hogfish dominate (138).
>
> | crop | frames | top-1 | balanced | dive-level vote | target-vs-Other AUC |
> |---|---|---|---|---|---|
> | human head/tail box | 290 | **76.6%** | 74.1% | 74.4% | 0.78 |
> | SAM 3.1 mask box at the dot (automatic) | 343 | **66.2%** | 64.9% | 69.2% | 0.77 |
> | masked (background zeroed) | 343 | 42.6% | 37.1% | 38.5% | 0.71 |
> | coral-gardeners "best of sam/masked" | 343 | 63.3% | 61.3% | 64.1% | 0.78 |
>
> **Where it goes wrong (confusion on the automatic crops)**
> - **Black Grouper: 0%** (31 frames). 19 are called Goliath Grouper and 8 Midnight Parrotfish.
> - **Parrotfish** get called Midnight Parrotfish: Stoplight 17/86, Blue 11/28, Rainbow 8/22.
> - **Hogfish: 82%.**
> - The list's two species absent from FishSense truth (E. morio, M. interstitialis) still
>   draw predictions.
> - **Blacked-out backgrounds hurt badly** (out of distribution for CLIP), which also drags
>   the "best of" rule below plain SAM crops.
>
> **Open set is weak.** Top-1 probability separates targets from "Other" at AUC 0.77–0.78, so
> a confidence threshold rejects non-target fish only poorly.
>
> **Next:** a linear probe or few-shot head on BioCLIP embeddings trained on our labels, with
> leave-one-dive-out evaluation, plus the list restricted to FishSense species and an "Other"
> class. The failures are consistent confusions, which suggests supervision will fix them.
>
> **Trained head, 2026-09-28** (`embed.py`, `probe.py`)
> - Class-weighted logistic regression on BioCLIP 2.5 embeddings (GPU L-BFGS). Classes are
>   the FishSense species plus OTHER.
> - Evaluated on the automatic SAM crops, each dive held out and predicted by a model trained
>   on the other dives (their SAM + head/tail crops).
> - λ is chosen by an inner leave-one-dive-out on the training dives only.
> - Hybrid: species the training dives cover on < 2 dives keep their rescaled zero-shot score.
>
> | model | targets top-1 | balanced | dive vote | Other recognised | 12-way |
> |---|---|---|---|---|---|
> | zero-shot | 66.2% | 64.9% | 69.2% | 0% | 52.4% |
> | trained head, λ fixed a priori (0.01) | 67.3% | 38.1% | 64.1% | 14% | 56.4% |
> | trained head, nested λ | 75.8% | 44.8% | 76.9% | 63% | 73.2% |
> | **hybrid, nested λ** | **77.6%** | **69.8%** | 76.9% | 53% | 72.5% |
>
> - **Per species (hybrid):** Hogfish 94%, Stoplight Parrotfish 86%, Nassau 68%, Blue
>   Parrotfish 61%. Black Grouper 26% and Rainbow Parrotfish 32% are still weak (2 and 4
>   dives respectively).
> - **λ:** the nested grid is {1e-5 … 1e-2}. Held-out dives chose 1e-5 on 12 of 16 and 1e-4
>   on 4; extending the grid lower changed nothing (75.5→75.8, 77.8→77.6).
> - **Limits:** 16 held-out dives, and Hogfish dominate. The single-dive species are carried
>   by the zero-shot fallback. More labelled dives of the grouper and parrotfish are what
>   would move this.

### E2 — Fully automatic length vs known length *(pillar 2; needs the bigger GPU)*

> **First fully automatic run, 2026-09-27** (`e2e_measurement/`: `run_e2e.py`, `score.py`).
>
> **Setup**
> - Production detectors, chained with no human input: laser detector `run3_epoch_021.pt`,
>   then SAM 3.1 (`sam3.1_multiplex.pt`) on the 1800×1350 dot crop, then the fishsense-core
>   keypointer, then production's depth/length geometry. Production itself never chains
>   these: it seeds head/tail and measures from human labels.
> - 1,528 frames of fish models and the ruler on 10 Aug 2023 pool dives (7 fish-model dives,
>   3 angle tests), with tape-measured lengths as truth.
> - Calibration pairs as in production (fish dive ← same-camera slate session). Label-free
>   = the E1j registration fit + |O| = 104.0 mm (the CAD stand-in).
>
> | step | dot | head/tail | calibration | frames measured | per-fish p90 MAE |
> |---|---|---|---|---|---|
> | A | human | human | slate | 100% | 3.0% |
> | B | auto | human | slate | 99.7% | 3.1% |
> | C | human | auto | slate | 92% | 10.2% |
> | D | human | human | label-free | 100% | 3.4% |
> | E | auto | auto | slate | 91% | 10.1% |
> | F | auto | auto | label-free | 91% | 10.5% |
>
> **Where the error comes from**
> - **Automatic dot vs human click:** median 0.8 px, p90 2.1 px, 1.7% over 20 px, none
>   missing.
> - **Head/tail coverage losses:** 108 frames with no mask (7%), 27 with the dot off every
>   mask (2%).
> - **Per-fish p90 MAE by model, fully automatic vs manual:**
>
>   | model | automatic | manual |
>   |---|---|---|
>   | Grouper | 3.7% | 3.3% |
>   | Snook | 4.9% | 2.7% |
>   | Purple Angel | 9.4% | 2.9% |
>   | Shark | 27.9% | 3.2% |
>
>   The ruler is never segmented as a fish, which is expected.
>
> **Why head/tail fails (overlays):** the head matches the human click every time. The
> keypointer's tail is the far end of the mask, which the humans don't use:
> - **Shark:** the tip of the upper caudal lobe instead of the fork.
> - **Angel:** a fin corner.
> - **Worst Grouper:** the mounting pole occludes the mask, so the tail stops at the pole.
>
> **Conclusion:** the dot and the calibration are solved to within 0.1–0.4 pts. The
> remaining gap is the tail keypoint convention (fork vs mask extreme) plus occlusion, all in
> the head/tail stage.
>
> **Tail study and reef fish, 2026-09-29** (`e2e_measurement/tail/`: `stage.py`, `gpu.py`,
> `keypoints.py`, `evaluate.py`)
> - **Frames:** 827 pool frames plus 791 real reef fish (8 calibrated dives, and green dives
>   362/366 at 200 each). Each frame was read once from the NAS on CPU; the GPU passes
>   (laser, SAM 3.1 at the auto and at the human dot) ran after.
> - **Fork rule** (production head; tail → deepest convexity defect in the tail third,
>   depth ≥ 3% L, fixed a priori): **no gain.**
>   - Pool per-fish p90 MAE 10.1% vs 10.2% production (Shark 27.8%, Angel 9.1% unchanged).
>   - It fires on only 19% of Shark masks (short lower lobe) and on 98% of Snook, where it
>     moves the tail 0.7% of L.
>   - Not tuned further on the pool test frames: that would be circular, and it would only
>     help non-REEF shapes.
> - **Reef keypoints vs human clicks** (human-seeded masks, production rule):
>   - head within 1.4% L (median), tail within 7.5% L;
>   - **pixel-length ratio median 1.005, MAE 5.9%**, 68% within 10%;
>   - head/tail swapped on 0.2%.
> - **Reef fully automatic vs manual length** (8 calibrated dives, same calibration):
>   **median +0.3%, MAE 5.4%, 62% within 5%, 82% within 10%.**
> - **Coverage is the reef gap.** SAM finds a fish under the human dot on 51% of reef frames
>   (pool: 92%), and an automatic length exists for 66% of calibrated-dive frames.
> - **Automatic dot on the reef:** median 0.9 px, p90 3.9 px (red) / 4.7 px (green). Green
>   gross misses (>20 px) run 3.5–8% per dive vs 0–1% red. Misses have median confidence
>   0.25 vs 1.0 for hits, and 64% sit below 0.9, so a confidence gate removes most.
> - **Revised conclusion:**
>   - On REEF target species the automatic head/tail is unbiased against humans (≈6% scatter).
>   - The pool's large errors are Shark/Angel model shapes.
>   - The remaining e2e problems are **coverage** (SAM on reef scenes) and **green-dot gross
>     misses**, not the tail rule.
>
> **Coverage diagnostic, 2026-09-29** (`tail/coverage_gpu.py`, `tail/coverage.py`)
> - **Method:** every SAM 3.1 mask ≥ 0.1 for "fish" / "reef fish" / "a fish" on the production
>   window at the human dot, 791 reef frames. SAM's upsampling is chunked (same output, bounded
>   memory).
> - **The earlier 51% was the wrong denominator.** 37% of reef frames (289) have a
>   head/tail label row with no coordinates: the labeller skipped them as not measurable.
>   SAM abstains on 84% of those, which agrees with the humans.
> - **On human-measured frames (502), production coverage is 71.9%** (red 91%, green 66%).
>   Misses:
>   - unseen: 67 (fish smaller, median 252 px vs 441 px covered);
>   - fish found but below the 0.5 cutoff: 64 (green 16% vs red 2%);
>   - dot just off the mask: 7;
>   - other: 3.
>
>   The other prompts and a dot tolerance recover almost nothing.
> - **Lowering the cutoff is a trade-off, not a fix:**
>
>   | cutoff | human-measured frames covered | human-skipped frames given a length | covered within 10% of human |
>   |---|---|---|---|
>   | 0.5 (prod) | 71.9% | 15.6% | 76% |
>   | 0.3 | 77.3% | 21.5% | 76% |
>   | 0.2 | 79.7% | 24.9% | 76% |
>   | 0.1 | 84.7% | 32.9% | 74% |
>
>   (The cutoffs were compared on these same frames.)
> - **Next lever: a measurability gate.** Humans skip frames for angle, curvature or partial
>   views, and `specieslabel` records `fish_measurable_category` / `fish_angle_category` /
>   `fish_curved_category`. A gate learned from those plus mask shape (silhouette ratio, edge
>   contact) would let a lower cutoff raise coverage without measuring unmeasurable fish.
>
> **Measurability gate, 2026-09-29: NO GAIN** (`tail/gate.py`)
> - **Setup:** logistic regression, leave-one-dive-out, on features available at run time
>   (SAM score, area, elongation, silhouette, solidity, edge contact, dot position, overlaps,
>   prompt agreement). Candidates are the 520 frames with any "fish" mask ≥ 0.1 at the dot.
> - **Result:** AUC measured-vs-skipped 0.73, carried almost entirely by the SAM score.
> - **At production's false rate** (15.2% vs 15.6%) it covers 66.7% of human-measured frames,
>   *below* production's plain 0.5 cutoff (71.9%). SAM's own confidence is already the best
>   mask-level gate; production sits near the frontier.
>
> **Per-fish coverage** (the unit REEF needs; same-fish clusters from `diveframecluster`,
> covering 313 of the 502 human-measured frames, median 2 frames per fish):
>
> | cutoff | clusters | fish with ≥ 1 automatic length | fish with ≥ 1 within 10% of the human |
> |---|---|---|---|
> | 0.5 (prod) | 98 labelled | **80.6%** | **73.5%** |
> | 0.5 (prod) | 149 predicted | 80.5% | 71.8% |
> | 0.3 | 98 labelled | 85.7% | 77.6% |
> | 0.3 | 149 predicted | 84.6% | 74.5% |
>
> The clustered subset has higher frame coverage (85%) than all measured frames (72%), so
> these are optimistic for the unclustered dives.
>
> **Automatic-dot gates, 2026-09-29: NOT NEEDED** (`tail/dotgate.py`)
> - **Confidence threshold:** chosen on T3 (1,115 frames, 221 dives, this study excluded) by
>   a rule fixed in advance (≤ 2% good dots lost) → 0.07.
> - **Line gate:** a dot > 25 px off the dive line fitted to the dive's *other* automatic
>   dots.
> - **On the 791 reef frames** (dot misses 4.6%: green 5.4%, red 0.7%):
>   - confidence catches 14/36 misses and loses 2.1% of good dots;
>   - line catches 24/36 and loses 7.9%;
>   - both catch 25/36 and lose 9.4%.
> - **End to end, calibrated dives (314 human-measured frames):** no gate gives 82.8%
>   coverage, MAE 5.4%, 3.1% > 20% off. Confidence: unchanged. Line: 79.9%, 5.3%, 2.8%.
> - **Why:** a mislocated dot rarely lands on a fish mask, so the existing dot-on-mask gate
>   already turns dot misses into abstentions. Keep the pipeline ungated; report the line
>   gate as an option that trades 3 pts of coverage for a slightly cleaner tail.

Automatic laser dot + automatic snout/fork (SAM3 laser crop) → length, on P1's rigid pool
targets. Compare against known length and against human-labelled length on the same
frames. This is the number that says whether the labels can be replaced.

### E3 — The human ceiling *(pillar 2; needs labellers, before December)*

T21, widened: the laser dot plus snout and fork, two or three labellers, overlapping
frames, **no pre-fill shown**.

### Supporting, deprioritized

T7 (frames per animal, range), T8 and T18 (roll test, really P4's), T12–T14 (mount
durability and printability), the TG-7 check. Mount printability shrinks to one question:
"holds `|O|` to about 15 mm and does not fail silently mid-dive."

---

> **Status 2026-09-25:** T1, T2, T3, T4, T5 (Mobile), T6, T7a/b and T8 have run. Results are in
> `p2-results.md`. **T1 changed the plan:** the 755 laser pairs are seeded copies, so T2
> became an anchoring measurement, and the laser ceiling moves into T21's collection.

Companion to `p2-inventory.md`; section references in the **closes** column point there.
Ordered by cost, not by importance. Within each tier, ordered by what unblocks the most.

Each test states what would count as a **negative** result, because several of these are
worth running specifically to retire a claim rather than to confirm one. A test whose
null result you would not report is not a test.

**Six are decision gates** — marked ⚑. Their outcome changes what P2 claims, so they
should run before the relevant section is drafted, not after.

---

## Tier 0 — analysis only, data already on disk

No fieldwork, no subjects, no new capture. Hours to a day each unless noted.

### T1 ⚑ Are the 755 doubly-labelled laser images independent annotations?

**Question.** `p2-inventory.md` §3.1 rests on 755 prod images carrying two laser labels.
Are those two *independent* annotations, or one annotation and a later correction?

**Data.** Prod `laserlabel`, read-only. Group by `image_id`, keep groups of ≥2.

**Method.** For each pair record: both `completed_by`, both `superseded`, both
`created_at`, and whether a `divelaserline` supersede event sits between them. Classify
as *independent* (two distinct labelers, neither superseded, no supersede event between)
or *correction* (same labeler, or one superseded, or a supersede event between).

**Decision.** Independent ≥ ~300 pairs → T2 is a genuine inter-annotator study and
`HANDOFF.md` §4.2's "the ceiling does not exist" is retired for the laser.
Mostly corrections → T2 becomes a *lower bound on disagreement* only, must be labelled
as such, and the head/tail collection study (T16) becomes the only real ceiling.

**Negative result is publishable**: "the corpus appears to contain repeat labelling and
does not" is exactly the trap §4.2 warned about, and worth one paragraph.

**Cost.** One SQL query + a classification script. An afternoon.
**Closes.** §3.1 caveat, §9 item 1.

---

### T2 ⚑ Laser-dot inter-annotator agreement (spatial)

**Gated on T1.** The thing the publication plan already assumes exists.

**Data.** The independent subset from T1.

**Method.** Three numbers, not one:
1. **Raw disagreement** — Euclidean distance between the two labellers' dots, full
   distribution (median, p90, max), not just a mean.
2. **Depth consequence** — push each pair through `triangulate_depth` with the dive's
   own extrinsics; report the resulting Δrange and Δlength in %. This is the number that
   reaches a measurement.
3. **Calibration consequence** — refit `LaserExtrinsics` per dive from labeller A's dots
   and from labeller B's, and report Δφ. P1's conversion (0.15° ≈ −2.0% length at 0.9 m,
   −4.5% at 2.0 m) turns that into a length error.

**Calibrate against what already exists**: 2.98 px x / 5.08 px y single-labeller line
scatter (§2.5); "humans are collinear to 2.9 px max" on dive 442 (§2.3); the gate's
10 px band (§2.3). If inter-annotator disagreement lands near 3 px, the human ceiling
and the detector's auto-accept band are the same number and that is the paper's headline
for component 2.

**Negative result.** Disagreement much larger than 3 px would mean the single-labeller
scatter understates the ceiling badly, and that the 93% byte-exact agreement figure is
measuring seeding, not correctness.

**Cost.** A day, given T1.
**Closes.** §3.1, §7B.1, and the §4.2 blocker in `HANDOFF.md`.

---

### T3 ⚑ Laser-detector miss rate, broken out

**Question.** The one you actually care about: how often is a dot present and the
detector returns nothing? Nowhere measured (§2.4).

**Design caution, load-bearing.** Do **not** aggregate `LaserPrediction.status` over
prod as it stands. The auto-accept docstring warns that predicted images "never received
a Label Studio task, a different population from the labelled ones." The honest design
is to run the detector over frames that already carry a **human** laser label and count
abstentions against them — the same oracle design `validate_headtail_predictions.py`
uses for head/tail.

**Break out by** — this is the whole point, the pooled number is not interesting:
wavelength (red vs green, §2.4b), environment (pool vs reef), range, detector version
(v1/v2), and camera unit.

**Why wavelength specifically.** P1 argues for green on detection-reliability grounds
and the corpus is 84% red (§2.4b). Either that rationale is supported or it is not, and
this is the only test that can say.

**Cost.** GPU inference over a few thousand frames. Not a one-minute job; budget a day
of compute plus a day of analysis.
**Closes.** §2.4, §7B.2, §7B.9, and P1's unsupported wavelength claim.

---

### T4 Cross-domain head/tail table

**Question.** Lite and Mobile errors are currently in incompatible units (§1.3).

**Method.** Renormalize the Mobile per-frame errors in
`2026-07-18_fishsense-core-test/data/v2_1_5.json` by human fish length from
`~/fishsense-mobile-recovery/mobile_headtail_project46.json`. Report snout and fork as
% of length in both domains, side by side.

**Expected.** The fork/snout ratio holds (~2.6× Lite, ~1.9× Mobile). If the *absolute*
percentages also land close, "one algorithm, two domains, comparable error" is a real
finding. If Mobile is much worse, the laser gate is doing the work and that is a
different — and more interesting — finding about why the domains are not symmetric.

**Cost.** Under an hour. Do this first; it is the cheapest item on the list.
**Closes.** §1.3, §7B.3.

---

### T5 Is the fork error a convention problem or a model problem?

**Question.** `headtail-prediction.md` §9.2, now cross-domain (§1.3).

**Method.** Decompose each fork error into components **along** and **across** the mask's
PCA major axis. A labelling-convention mismatch (labeller clicks the notch, detector
returns the mask extremity) is a tight, signed, along-axis offset. A model failure is
scattered in both. Run on both domains.

**Decision.** Tight along-axis offset → a constant correction fixes 7.4%→~2.8% for free,
and the detector section becomes much stronger. Scattered → say so and stop trying.

**Cost.** Half a day. Data is in hand for both domains.
**Closes.** §7B.6.

---

### T6 Landmark-placement noise bound from the P1 corpus

**Method.** `HANDOFF.md` §5 item 1, unchanged and still not done. Within a
(session, target, narrow range bin), the spread among the *best-presented* frames bounds
one labeller's landmark noise. Read `corpus.csv` with
`fishsense_imwut.calibration.load_rows`.

**Why it still matters.** It is not the inter-annotator ceiling, but it is a cheap upper
bound that puts a number behind P1's near-range Weasly Fish claim, and it is the only
landmark-noise figure obtainable without new labelling.

**Cost.** A day.
**Closes.** §7B.5.

---

### T7 Diver compliance against P1's own three instructions

**Question.** P1 claims "no specialized training" while issuing three instructions
(§6.6). Were they followed?

**Three sub-tests, increasing difficulty:**
- **T7a — frame count.** Already answered in P1's handoff: median 2 frames per animal,
  max 8, against an instruction of ≥10. Needs writing up, not computing.
- **T7b — range.** Distribution of laser range on field frames against the ">1 m"
  recommendation. One query on `corpus.csv`.
- **T7c — pose.** Needs the scale-free mask pose estimator from
  `HANDOFF_TO_P2.md` §2, validated on the 1,428-frame angle experiment first. This is
  the real work, and it has its own validation set already.

**Why this is the paper's spine.** The gap between instruction and behaviour *is* the
deployability measurement, and it lives inside P1's own corpus rather than requiring a
new study.

**Cost.** T7a free, T7b an hour, T7c a week including validation.
**Closes.** §6.1, §6.6, §7B.10.

---

### T8 Finish the roll test

**Method.** `roll-test-for-camera-ready.md`, verbatim. Compute LEGO-vertical intrinsics
(cap refit at 2 iterations or it times out), apply
`sensor = sqrt(r_h · r_v)`, `target = sqrt(r_h / r_v)`, cross-check against the
checkerboard pair.

**Decision.** Target-side → the E4E board's printed pitch is anisotropic, a moulded brick
target is *better* on this axis, and `HANDOFF.md` §7's argument lands. Sensor-side → the
fleet-wide fx/fy = 0.99141 ± 0.00044 is real and the board is exonerated.

**This is P4's camera-ready fix more than P2's**, but P2 inherits the answer either way.

**Cost.** Hours of compute, a day total. Data is in `~/data`.
**Closes.** §5.2, §7B.4; P4's Limitations.

---

### T3b Laser-detector fixes that need no retraining — *analysed 2026-09-25, see `p2-results.md` T3*

Threshold retuning is not a fix. Passing the wavelength (+2.2 pt) and gating on the dive's
own laser line at inference (halves wrong-spot dots, −84 % false alarms) are. Both use
information the pipeline already has. **Next step:** implement both in a branch of
fishsense-lite and re-run `run_detector.py` with a per-dive line; the leave-one-out lines
here are an upper bound on the gate's cost. Retraining (T3c) needs the training repo.

### T9 SAM3 prompt ablation

**Method.** Re-run the §1.2 backend comparison with `["fish", "small fish"]` — the
coral-gardeners default — against the single `["fish"]` prompt every reported number
used. Same 80 frames, same labels.

**Why.** `headtail-prediction.md` §0.6 flags it as untested, and prompt choice is a free
parameter that could move coverage more than the crop-size sweep did.

**Cost.** An hour of GPU. Genuinely cheap.
**Closes.** a stated limitation in §1.2.

---

## Tier 1 — bench tests on the hardware

These need the physical mount and a fixed target. No divers, no water (except T12).
**All of them are gated on you handing over the mount** (§4.2). Days each.

### T10 ⚑ Cold-shoe remount repeatability

**The single most decisive cheap test on this list.** P1 makes a precise, falsifiable
claim: play is "mostly around the vertical y-axis" and "changes between dives but not
within a dive" (§4.0).

**Method.** Fixed target at a known range, camera on a tripod.
- **Between-mount:** unmount and remount the laser 20 times; after each, capture a burst
  and fit the laser line. Report the spread of φ and of the dot position.
- **Within-mount:** without touching the mount, capture the same burst 20 times over an
  hour. Report the same spread.
- **Axis:** decompose the between-mount variation into yaw / pitch / roll.

**Decision.** Between-mount ≫ within-mount → P1's claim is confirmed *and quantified*,
and per-dive calibration is demonstrably necessary rather than merely prudent. Comparable
→ something else dominates and P1's attribution is wrong. Variation not concentrated in
yaw → the "mostly around the vertical y-axis" claim is wrong.

**Compare against** P1's observed 0.27° across seven sessions and 0.82° within one
session (§4.3). If 20 remounts on the bench reproduce 0.27°, the cold shoe explains the
field drift entirely and the PLA claims are unnecessary.

**Cost.** One day. Needs no water and no dive.
**Closes.** §4.0 cold-shoe claim; bounds how much of §4.3's drift is mechanical.

---

### T11 ⚑ Laser diode cone

**Question.** P1: rotating the laser within the mount sweeps the beam through a cone
(§4.0). Never quantified, and it sets how precisely a diver must index the pointer.

**Method.** Fixed target, fixed range. Rotate the laser about its body axis through 360°
in ~15° steps, capturing at each. Fit a circle to the dot locus; the radius gives the
cone half-angle.

**Decision.** This is a **protocol number**: cone half-angle × 2 is the worst-case φ
error a diver introduces by reinserting the pointer at a different clock position. If it
is comparable to the 0.15° that costs 4.5% at 2 m, then **"mark the pointer's rotational
index"** becomes a one-line addition to the deployment protocol with a measured
justification — a concrete, cheap deployability win.

**Cost.** Half a day. Repeat on 2–3 pointers; diode misalignment is per-unit.
**Closes.** §4.0 diode claim; produces a protocol recommendation.

---

### T12 PLA thermal creep

**Method.** Measure the mount's critical dimensions (calipers) and φ (T10 rig). Soak at
a realistic abuse temperature — a car dashboard or a closed dive bag in sun, 50–60 °C —
under the laser's own mounted load, for a realistic duration. Re-measure at intervals.
Run a loaded and an unloaded specimen; creep is load-dependent and PLA's glass transition
is ~60 °C, so this is a real effect, not a hypothetical.

**Decision.** If φ shifts beyond 0.15° after a plausible exposure, P1's sun/heat warning
is quantified and **"do not leave the rig in the sun"** becomes an evidenced protocol
line. If not, P1 should soften the claim.

**Cost.** Days of elapsed time, hours of work. Needs ≥3 specimens to say anything.
**Closes.** §4.0 creep claim.

---

### T13 PLA water absorption and embrittlement

**Method.** Mass gain over immersion time in salt water (and fresh, as control) on
printed coupons; periodic flexural or simple drop test; φ stability on a mounted
specimen. Include screw-boss pull-through force before and after soak, since that is the
specific failure P1 names.

**Honest caveat.** PLA hydrolysis at seawater temperature is slow. A realistic timeline
is weeks to months, and an accelerated elevated-temperature version confounds creep with
hydrolysis. **This is the slowest test on the list — start it first and let it run**,
or scope it down to "does a mount that has lived in salt water for a season differ from
a fresh one", which is a retrospective test on units you already have.

**Cost.** Weeks elapsed. Start now or descope.
**Closes.** §4.0 water-absorption and cracking claims.

---

### T14 ⚑ Printability across printers and materials

**This is the component-4 test that is actually about deployability**, as opposed to
T10–T13 which are about durability.

**Question.** A citizen scientist prints the mount on *their* printer in *their*
filament. Does it still work?

**Method.** Print the same STL across a realistic spread — 3–4 printers, PLA / PETG /
ASA, 0.15 vs 0.25 mm layers, 2 vs 4 walls. For each: measure the fitted `|O|` and φ, and
the cold-shoe fit. Compare against the 15 mm tolerance on `|O|` that `HANDOFF.md` §7
says any printed mount meets.

**Decision.** All inside 15 mm → **the strongest single deployability result P2 can
produce**: the mount is genuinely commodity and self-calibration absorbs the rest. Some
outside → there is a print-settings specification, and it must ship with the STL. Either
outcome is a result; the second is more useful to a real programme.

**Cost.** A week including print time, more if you widen the matrix.
**Closes.** §4 as a whole; turns `HANDOFF.md` §7's assertion into a measurement.

---

### T15 Checkerboard pitch anisotropy

**Method.** Caliper the E4E board's pitch **per axis**, several places, on several
boards. Then calibrate one camera unit against the same board in landscape and in
portrait.

**Decision.** Settles whether the fleet-wide fx/fy = 0.99141 ± 0.00044 is the board's
printed pitch (feed-axis scaling) or the sensor. Pairs with T8 from the other direction
— agreement between the two is strong evidence; disagreement means something else is
going on.

**Also produces** the missing square-size measurement that
`checkerboard-laser-calibration.md` §0.4 calls "the single number that can silently
wreck every length this produces."

**Cost.** An afternoon of measurement, a day of calibration.
**Closes.** §6.4, §7A.4; the P1/P4 anisotropy correspondence.

---

## Tier 2 — new capture, no human subjects

### T16 ⚑ Calibration capture-protocol ablation

**The test that turns §5's gap into P2's contribution**, and my pick for the highest
value-per-day on this list.

**Question.** What is the *minimum* capture a recreational diver can be asked for, and
what does each shortcut cost?

**Method.** Shoot one deliberately **rich** capture of the brick target — wide pose
spread, both rolls, near and far, 60+ views. Then **subsample it in software** to
simulate protocols:

| simulated protocol | views | roll | pose spread |
|---|---|---|---|
| "what the existing capture was" | 21 | none | ~15° |
| naive diver: one burst, one pose | 10 | none | <5° |
| naive + told to move around | 15 | none | ~30° |
| + told to rotate the camera | 15 | two rolls | ~30° |
| rich reference | all | all | all |

For each, report fx, fy, fx/fy, principal point, **and the delivered length** on the
same held-out decoy frames — the last column is the one that matters, per P4's finding
that a 2.25% focal error costs 0.016 pp.

**Output.** A protocol card: *"shoot N views, move this much, roll the camera once."*
With numbers behind every clause. That is a deployability artifact, not a calibration
result, and no other paper is positioned to produce it.

**Negative result.** If delivered length is flat across every protocol, that is *better*
news and a cleaner paper: the capture does not matter for this measurement, say so
loudly and stop asking divers for anything.

**Cost.** One good capture session (half a day) plus a few days of analysis. The
subsampling means one shoot answers every protocol variant.
**Closes.** §5.3 — the missing capture protocol, the largest true hole in component 5.

---

### T17 Lever-arm protocol test

**Question.** P1: "two observations a metre apart pin the axis far better than sixteen
at one distance, and a burst shot at a single distance does not pin it at all" (§5.3).
Stated as physics, never demonstrated end to end.

**Method.** Same dive/session: shoot a slate calibration as a single-range burst, and a
second spanning ≥2× range. Fit both. Measure both against the *same* held-out targets at
a *third* range.

**Expected.** The single-range fit is accurate at its own range and wrong away from it —
P1 reports exactly this pattern (−17.25% and −127.6% for bursts predicting each other's
distance). Reproducing it deliberately makes "photograph the slate at two distances" an
evidenced instruction rather than a derivation.

**Cost.** One pool session plus analysis.
**Closes.** the protocol half of §5.3; feeds T16's card.

---

### T18 Checkerboard Horizontal, same session

**Method.** The missing fourth capture (§5.2). Completes the roll decomposition with a
same-session checkerboard pair, removing the "different sessions, possibly different
units" caveat that currently blocks T8's cleanest comparison.

**Cost.** An hour, if T16's session is already happening. **Piggyback it.**
**Closes.** §7A.3.

---

### T19 Does the port model transfer to a second housing?

**Question.** The hardware-specificity barrier is the one row of `HANDOFF.md` §1 that
**no paper owns** (§10). P4's only statement is "it *should* transfer to other flat-pane
housings, but we have not tested that."

**Method.** Borrow or buy a second flat-port housing — ideally a different manufacturer,
not just a second PT-059. Calibrate in air, apply the same unmodified Pinax correction,
and run the homography-residual-vs-field-angle test (P4 §4) plus a delivered-length check
on the calipered decoy.

**Decision.** Residual flat across the frame on housing #2 with no retuning → the
correction is a property of flat ports, the hardware-specificity barrier drops, and P2
has a contribution P4 explicitly declined to claim. Residual grows → the barrier is real
and must be reported as such, which is equally publishable and more honest.

**Cost.** A housing, plus a day. The cheapest way to claim an entire barrier.
**Closes.** §10's unowned row; §7A's hardware-specificity gap.

---

### T20 Bubble incidence under the corrective optic

**Method.** Retrospective first — audit N frames per dive across the existing corpus for
visible bubbles under the optic, and count dives lost or degraded. Prospective only if
the retrospective rate is non-trivial.

**Caveat.** P4 removes the optic, so this measures a barrier that is already on its way
out. Run it only if P2 wants the invisible-at-collection-time failure class (§6.5) as a
framing device and needs a rate to anchor it. **Otherwise skip** — it is the most
skippable item here.

**Cost.** A day of image audit.
**Closes.** §7A.5.

---

## Tier 3 — human subjects

Weeks, and they need design before they need execution. **Do not start these until
T1–T5 are done**, because T1/T2's outcome changes what the agreement study needs to
cover and T4/T5's outcome changes what the pre-annotation trial is testing.

### T21 ⚑ Head/tail **and laser-dot** inter-annotator agreement study

> **Widened 2026-09-24 by T1:** prod has no independent laser pairs either. Add the laser
> dot. It is cheap (median 12.9 s per label). **Collect it with no pre-annotation shown**, or
> T2's anchoring makes the pairs copies again.

**The one genuine collection gap in your four components** (§3.2): 11 doubly-labelled
images in prod, 4 in Mobile.

**Design.** Overlapping assignment — every frame to ≥2 of K labellers, K drawn from the
32 high-volume pool. Not a separate task; **inject the overlap into the normal queue** so
labellers do not know which frames are duplicated. Cover both domains: Lite underwater
and Mobile in-air, since the detector spans both and the agreement may not.

**Sizing.** `MEASUREMENTS.md` gives the variance structure (head/tail residual SD 0.752,
labeller 12.6%, dive 7.8%) and 179/arm for a 20% *time* effect. Agreement needs its own
power calculation — but T2's laser result will give you the effect size to plan against,
which is another reason T1/T2 come first.

**Report.** Snout and fork separately, in px and in % of length, so it is directly
comparable to §1.2's 2.8% / 7.4% and to T4's cross-domain table. **The fork number is
the interesting one** — if human labellers disagree on the fork by ~7% of length, the
detector is already at the ceiling and component 1's story inverts completely.

**Cost.** A few hundred frames × 2–3 labellers. Weeks elapsed, low effort per person.
**Closes.** §3.2, §7A.1, `HANDOFF.md` §4.2 for head/tail. **Do it before the December
defence**, per §4.2.

---

### T22 Does pre-annotation save labeller time?

**Design.** `headtail-prediction.md` §8, unchanged: ship dark for a week writing
`HeadTailPrediction` rows with no seeding — which also re-measures §1.2 on current data
— then enable seeding on one dive.

**Metrics.** Labeller time per task and the rate at which seeded points are **moved**.
Explicitly *not* agreement with the model, which is circular.

**Randomize within labeller** — labeller identity explains 12.6% of head/tail time
variance and up to 40.3% for laser (§6.3). Between-subject assignment will not survive
that.

**Power.** 179 annotations/arm for a 20% effect, already computed (§6.3). Note §6.3's
warning: detecting the same effect via *skips* would need ~4,446/arm. Use time.

**Cost.** Two weeks elapsed, mostly waiting.
**Closes.** §7A.6; `headtail-prediction.md` §9.1, the stated real success criterion.

---

### T23 The untrained recreational diver

**The actual P2 question**, and correctly scoped as future work in `HANDOFF.md` §0.

**Do not skip designing it just because you will not run it.** A paper that says "REEF
volunteers are trained volunteers inside a structured programme and are not a proxy for
unsupported recreational use" is much stronger if it also says what the study *would* be:
recruitment, the tasks, what is measured (time to first usable measurement, compliance
with the three instructions from T7, calibration success rate, drop-out), and why the
existing corpus cannot substitute.

**Cost.** Design only, for this paper.
**Closes.** §7A.7 — by scoping it honestly rather than by filling it.

---

## Suggested order

**This week, no dependencies:** T4 (an hour), T1, then T2 and T3.
T4 first purely because it is nearly free and gives you the cross-domain table
component 1 currently lacks.

**Start T13 now regardless** — it is the only test whose elapsed time you cannot
compress.

**As soon as the mount arrives:** T10 and T11, in that order. Both are one-day bench
tests, both quantify a claim P1 has already published unsupported, and T11 produces a
protocol line on its own.

**One capture session buys three tests:** T16 + T18 + T17 if the pool is available.
Shoot rich, subsample later.

**Before drafting component 1:** T5, then T21's design.
**Before drafting component 4:** T14 — it is the deployability test, where T10–T13 are
the durability tests.
**Before drafting component 5:** T8 and T16.

**The six gates,** in the order their answers are needed:
T1 → T2 (what component 3 can claim) ·
T3 (whether component 2 has a result at all) ·
T14 (whether the mount is commodity) ·
T16 (whether P2 can ship a protocol) ·
T10 (whether P1's mount attribution is right) ·
T11 (whether a protocol line follows).
