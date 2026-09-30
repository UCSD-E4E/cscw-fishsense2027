# E1: laser calibration with nobody labelling (pillar 1)

`p2-tests.md` E1. Refits P1's 23 calibration dives (12 slate, 11 checkerboard) with
**production's own stage-13 code and refusal gates**, loaded by path from fishsense-lite,
swapping only where the inputs come from. Each calibration is scored the way P1 scores
one: re-triangulate every corpus frame that used it, and compare the per-model p90
against the known length. Known lengths are only ever the check.

| file | what |
|---|---|
| `e1.py` | inputs, production kernel, gates, evaluation; `python e1.py stages` prints the ungated table |
| `run_frames.py` | per-frame NAS pass: detector dot, slate estimates, checkerboard corners |
| `frames.csv` | 656 frames: slate-labelled frames of the slate dives, ≤30 laser-labelled frames per checkerboard dive |
| `frames_out.jsonl` | its output, 656 records, 0 errors |
| `gated_results.csv` | every stage × dive through production's gates; pinned by `tests/test_e1.py` |

Run from P4's environment (OpenCV + `fishsense_core` 4.0.0, production's pin). The NAS
pass also needs torch and pymupdf overlaid; see `run_frames.py`.

## Checks on the harness

- **Depths:** the stored calibrations reproduce P1's recorded depths to within 2.6 mm
  on all 2,927 frames.
- **Refit:** production's code on the human inputs reproduces 8 of 12 stored slate
  calibrations exactly (0.0000°). The other 4 differ slightly, most likely because
  their labels changed after the stored fit. The largest effect is 0.26 pp on a
  corpus cell.

## Result: production's gates applied (geometry, self-consistency, baseline)

| | dives | accepted | refused | accepted but >2 pp off | median p90 error |
|---|---|---|---|---|---|
| **checkerboard, fully label-free** | 11 | **11** | 0 | **0** | 2.17 % (identical with human dots) |
| slate, human corners + detector dots | 12 | 9 | 3 | **0** | 3.25 % |
| slate, predicted corners (ECC ≥ 0.8) + detector dots | 12 | 6 | 6 | 2 (62; 436 = V-Slate 2, unsupported) | 2.38 % |
| *reference: slate, all human* | 12 | 11 | 1 | 0 | 2.74 % |

Adding production's fourth gate, "the calibration describes the dive", changed nothing
here; the first three decide everything on these dives.

1. **A checkerboard dive calibrates with no human at all, today.** Its corners were
   always automatic, and the detector replaces the labelled dot with no change in
   accuracy. So a label-free laser calibration already exists in production's own code,
   provided the target is machine-readable.
2. **Detector dots are safe in calibration.** On slate dives they cost 2 of 11 accepted
   calibrations, which are refused, never silently wrong. Dive 77's specular reflection,
   named in production's code comments, is among those caught.
3. **The duct-tape slate is what needs a human.** Predicted slate corners pass only 6 of
   12 dives and let one supported dive (62, 2.1 pp) through wrong. This is the
   predictor that was retired for false fits on these same pool dives.

**Design consequence, with the duct-tape slate kept.** The slate was chosen because it
is approachable, and a printed or fabricated target reintroduces exactly what P4
removed. *(A "machine-readable panel" recommendation was drafted here and withdrawn
2026-09-25 for that reason.)*

The checkerboard result shows the kernel and gates are ready. The remaining human step
is **the duct-tape slate's corners**. Three routes keep that slate:
1. **Label fewer frames.** The lever arm, not the count, pins the fit (P1), so 2–3
   frames at spread ranges may suffice. Testable from existing labels.
2. **A better duct-tape corner finder**, using 326 human-labelled frames, with the
   dive's laser line as an extra gate.
3. **No slate at all:** E1c (dot size) or scale-free self-calibration on rigid objects.

## Limits

- **Pool dives only**, all 2023 and red lasers. Reef turbidity and green lasers are
  untested for board detection.
- **Checkerboard frames were sampled at 30 per dive.** Dive 509 has only 4 usable
  board + dot frames in the sample.
- **The "describes the dive" gate used human dive dots as a stand-in** for running the
  detector on every frame. It changed nothing, so that stand-in doesn't matter here.
- **A printed board is exact only to its printing.** The E4E board is square to 0.28 %
  and its pitch was calipered on 2026-09-16 (T8, T15).
