# T3: laser-detector miss rate, by wavelength and environment

> **Done 2026-09-25.** Results are in `recall.ipynb` and `p2-results.md` T3.
> `predictions.csv` is the raw output: 2,792 rows, 0 errors.

`p2-tests.md` T3. **Was waiting on:** the detector checkpoint `run3_epoch_021.pt` (verify
sha256 `bd3ab8f5e273da37a1f2dfc2c6c6a36735b89ae26ff821b71b1f8acce3a74d68`, pinned in
`fishsense_core/_laser_detector.py`), the detector's **train/val split**, and the GPU.

## The oracle: human dots drawn without a seed

T1/T2 showed that labels made from a pre-annotation are copies of the seed (87 % are
accepted unchanged). Scoring a detector against them is circular, so the oracle is only
annotations with `origin == "manual"` and no `parent_prediction`, plus the "no dot"
submissions as negatives.

On the 2026-09-25 backup that gives **46,217 images**, earliest unseeded label per image,
from `../sql/extract_laser_annotations.sql`:

| | other | pool | reef | total |
|---|---|---|---|---|
| green | 7 | 51 | 8,693 | 8,751 |
| red | 1,447 | 817 | 33,127 | 35,391 |
| no dot | 1 | 347 | 1,727 | 2,075 |

`environment` is a keyword heuristic on dive path and name: pool/Canyonview/Host01 →
pool, pier → pier, REEF/Alligator/Keys → reef, anything else → other. It is good enough
to stratify with, not to report as ground truth.

## `sample.csv`

**1,574 frames over 249 dives.** Targets per (wavelength, environment) cell: reef red 400,
reef green 400, pool red 300, pool green 51 (all of it), other red 100, reef none 200,
pool none 150. Each cell is capped at **12 frames per dive** so no single dive dominates,
which is why the pool cells come in under target (red 277, green 47). Seed 20260924 + cell
index. `raw_path` is resolved on `~/mnt/fishsense_data` and was found for 1,571 frames
(3 reef-red files are missing).

Dive paths resolve under `REEF/data/` (479 dives) or carry an absolute
`/fishsense_data/` prefix (43). Three "split" pseudo-dives resolve only per image.

## Scoring plan

- **Recall** (your metric): share of dot frames where the detector returns a dot within
  R px of the human dot, R ∈ {3, 10}. "Returns nothing" and "returns a dot elsewhere"
  are reported separately, because they are different failures.
- **False-positive rate:** share of "no dot" frames where it returns a dot.
- **Break out by** wavelength, environment, camera and range. The wavelength split is
  what tests P1's "green for reliable detection" rationale.
- **Excluded:** images in the detector's training set, once the split is known. Most of
  these 46k labels predate the 2026-05-02 training repo, so the overlap could be large.
  Without the split, only images labelled after training are safe to use, and after May
  2026 almost all labelling was seeded.
- **Canvas:** labels on the old 3987-wide canvas share the rectified 4014 pixel frame.
  T1 shows detector-to-human distance of ~1.4 px on both canvases.
