# Roll test: is the ~1 % fx/fy anisotropy the sensor or the target? (T8)

`p2-tests.md` T8, which finishes `../wuwnet-fishsense2026/correspondence/roll-test-for-camera-ready.md`.
This is more P4's camera-ready work than P2's. It lives here because that is where it
was run, so move it if P4 wants it.

**Run from P4's environment**, which has OpenCV, the raw decoder and `fishsense_wuwnet`:

```bash
../../../wuwnet-fishsense2026/.venv/bin/python build_correspondences.py   # ~6 min, needs ~/data ORFs
../../../wuwnet-fishsense2026/.venv/bin/python fit_roll.py                # ~5 min, reads the caches here
```

`lego_V.npz` and `cb_V.npz` are the cached correspondences, so `fit_roll.py` runs
without the raw images. `roll_results.json` is its output.

## Result: not settled, and the note's "strong hint" does not survive

Decomposition: `r_H = s·t`, `r_V = s/t`. `s` is the sensor ratio and survives a 90°
roll; `t` is the target ratio and inverts.

| pair | distortion held fixed from | r_H | r_V | sensor s | target t |
|---|---|---|---|---|---|
| **LEGO, same session** (clean) | same-session vertical checkerboard | 0.99771 | 0.98550 | **0.99158** [0.98536, 0.99642] | **1.00618** [1.0013, 1.01255] |
| LEGO, same session | 2024 garage checkerboard (the paper's choice) | 0.99886 | 0.99483 | 0.99685 [0.99029, 1.00245] | 1.00202 [0.99717, 1.00831] |
| checkerboard, isotropic model | own fits | 0.99311 | 1.00780 | 1.00043 | 0.99268 |
| checkerboard, calipered model | own fits | 0.99030 | 1.01059 | 1.00040 | 0.98991 |

Brackets are 95 % view-bootstrap intervals (300 resamples). The checkerboard rows are
**cross-session**: H is the 2024 garage set, V is 2026-09-21. The same-session
horizontal board that would make them clean was never shot (T18).

Reading it:

1. **The clean LEGO pair points to the sensor, not the board.** With same-session
   distortion the sensor term is 0.9916, excluding 1 and sitting on the fleet-wide
   0.99141 ± 0.00044 from P1. The note's hint pointed the other way.
2. **But it depends on which distortion is held fixed**, by more than its own interval:
   swap in the garage distortion and both terms become indistinguishable from 1. The two
   distortion fits differ mainly in k2 (−0.081 vs −0.054). A brick tower spans too little
   depth to fit distortion itself (P4 §5), so this cannot be resolved from the LEGO data
   alone.
3. **The checkerboard pair points to the board and is internally inconsistent** with the
   LEGO's sensor estimate. Given s = 0.99158, the board term implied by H is 0.99871
   (calipered) and by V is 0.98119. A single board term needs those to be equal. Across
   the two sessions the principal point also moves by ~70 px in x and ~80 px in y, so
   something besides roll differs. The session confound is real.
4. **The calipered pitch makes the board's apparent anisotropy larger, not smaller**
   (t 0.9927 → 0.9899). **This is not a code bug.** I checked it:
   `board_object_points` puts the long pitch (42.231 mm) on the 14-corner axis, and in
   the detector's output corners 0→13 run along the board's long side (1,305 px against
   670 px for the other side on a garage frame). So the calipered correction is applied
   to the right axis and still goes the wrong way. Either the calipered numbers do not
   capture the board's effective anisotropy (0.28 % is 1.5 mm over 549 mm), or the
   anisotropy is not in the pitch at all. A bowed or unevenly mounted board would do it.

**The focal lengths themselves swap under roll on the checkerboard.** Upright 2024 gives
fx 2955 / fy 2984; rolled 2026 gives fx 2990 / fy 2958. That is the target-side
signature, visible without any decomposition. It is why the hint looked strong, and it is
still cross-session.

## Things that were wrong or fragile along the way

- **4 of 14 rolled LEGO views have mismatched correspondences**: P9210052 (20 points,
  ~740 px median error), P9210044 (68 px), P9210053 (44 px), P9210045 (13 px). Only
  1 of 21 upright views fails the same screen (P9210013, 13 px). The matcher in
  `target_detect.match` is much less reliable on rolled views.
  **Unscreened, those four views fabricate a strong target-side flip** (r_V = 1.00733,
  t ≈ 0.995). An earlier pass of this analysis briefly reported exactly that. Views are
  now dropped when their own PnP fit has a median error over 10 px, applied identically to
  both orientations. Then two rounds of point-level 3-MAD rejection follow, which is
  what the note's "cap outlier rejection at 2 iterations" referred to.
- The **P2 consequence**: T16's protocol card will want to say "roll the camera once".
  Until the matcher handles rolled views, asking a diver to roll the camera produces
  bad correspondences 29 % of the time.

## Reproduction checks

| check | expected | got |
|---|---|---|
| rebuilt upright views vs P4's `lego_target_raw.npz` (3 frames) | identical | identical (image points to 0.00 px, with `subpixel=False`) |
| garage board fx/fy, calipered pitch | 0.99030 (note) | 0.99030 |
| paper's brick-vs-board ratio offset, plain fit | +0.79 % (P4 §5) | 0.99809 / 0.99030 = +0.787 % |
| note's LEGO H, robust fit, same-session distortion | 0.99773 @ 5.4 px | 0.99771 @ 5.46 px |
| note's vertical checkerboard, isotropic | 1.00801 on 18 views | 1.00780 on 17 views (2 frames give no corners here) |

The note also said the vertical LEGO solve "kept timing out". It does not: each
non-planar solve takes seconds. The earlier failures were probably the four broken
views sending the optimiser to a 2,540 px RMS solution.

## A camera that looks isotropic, and why it is not evidence

In the production intrinsics, cameras 1–6 and 10 average fx/fy = **0.99141**, which
reproduces P1's fleet figure exactly. Cameras 8, 9 and 11 sit at 0.991–0.992. **Camera 7
(FSL-08) reads 1.00010**, but it has no serial number and no dives in the database, so it
looks like a placeholder rather than a calibrated unit.

**FSL-08 and later units are TG-7s** (per the project lead, 2026-09-25; EXIF confirms `TG-7` on
FSL-10/11). The other TG-7s (FSL-09/10/11) read 0.991–0.992, the same as the TG-6s,
so **the camera model does not explain FSL-08's 1.0001; its calibration does.** There is no
FSL-08 lens-calibration dive in the pipeline and no FSL-08 folder on the NAS to depth 5,
so its intrinsics were made outside the pipeline, by an unknown procedure. The unit is
in hand.

## What would settle it

1. **T18: the same-session horizontal checkerboard.** It turns the checkerboard rows
   into a clean pair and removes the session confound. **Best done on FSL-08**:
   checkerboard and LEGO, each upright and rolled 90°, in one session. That settles T8
   and FSL-08's odd 1.0001 together. **No existing capture substitutes.** Every 10th frame
   of the TG-7 lens-calibration sets (FSL-10D, 151 JPGs; FSL-11D, 205) is upright (EXIF
   orientation 1, 37 of 37 sampled).
2. **Fit distortion jointly** from horizontal and vertical board views of one session,
   instead of borrowing it from one orientation. That removes finding 2.
3. **More rolled LEGO views**: 10 usable is thin, and r_V's interval is 2–5× wider
   than r_H's.

None of this reaches delivered length. P4 §5 puts the whole anisotropy at 0.137 pp.
