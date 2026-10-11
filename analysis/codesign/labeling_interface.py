"""The image a laser labeller sees, rebuilt with production's own preprocessing (figure: labeling interface).

Production (fishsense-lite data-processing worker, activities/preprocess_laser_image.py) decodes the
camera RAW, undistorts it with the camera's intrinsics and boosts contrast with CLAHE
(fishsense_core RectifiedImage), draws the expected-laser region as a 2-px green closed outline
(overlay_laser_region_and_encode_jpeg; "an outline, never a fill: the labeler has to see the image
under it"), and encodes a JPEG. This script calls those same functions; nothing is re-implemented.

  frame    image 102654: a typical reef Hogfish (Fig 13's example), dive 349, green laser, dot inside
           the region. RAW copy from the local stage cache (~/.cache/cscw-fishsense2027/tail_stage).
  region   fishsense_shared.laser_region.LASER_REGION_POLYGON (one fleet-wide polygon, pinned with the
           detector version)
  intrinsics  laser_detection_analysis/intrinsics.csv (camera 6)

Writes analysis/codesign/figures/labeling_interface_full.jpg (the JPEG bytes as production makes them)
and labeling_interface{,_inset}.{pdf,png}: the image at column width, plain and with a zoomed inset of
the dot. In the figure only, the region outline is redrawn at 0.8 pt (the width of the zoom lines) so it survives scaling (production
draws 2 px on the 4014-px image), and the inset, its box and connectors are ours, not part of what
labellers see.

Run from fishsense-lite's venv (fishsense_core, the worker package and temporalio installed):
  ../fishsense-lite/.venv/bin/python analysis/codesign/labeling_interface.py
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "figures"
IMAGE_ID, CAMERA_ID = 102654, 6
RAW = Path.home() / ".cache/cscw-fishsense2027/tail_stage" / f"{IMAGE_ID}.ORF"
ONE = 3.33   # ACM column width, inches
OUTLINE_PT = 0.8   # figure-only outline width, matching the white zoom lines; production draws 2 px


def production_jpeg() -> bytes:
    import csv
    from fishsense_data_processing_workflow_worker.activities.preprocess_laser_image import _rectify_overlay_encode
    from fishsense_shared.laser_region import LASER_REGION_POLYGON
    row = next(r for r in csv.DictReader(open(REPO / "laser_detection_analysis/intrinsics.csv")) if int(r["camera_id"]) == CAMERA_ID)
    return _rectify_overlay_encode(RAW.read_bytes(), json.loads(row["camera_matrix"]), json.loads(row["distortion_coefficients"]),
                                   bbox=(0, 0, 0, 0), region=LASER_REGION_POLYGON)


def figure(jpeg: bytes, inset: bool):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    img = cv2.cvtColor(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    fig, ax = plt.subplots(figsize=(ONE, ONE * h / w))
    ax.imshow(img, interpolation="lanczos"); ax.set_axis_off()
    # production's outline is 2 px on a 4014-px image, too thin once scaled to a column: redraw the same
    # polygon in the same green at a print-visible width (the caption says the outline is thickened)
    from fishsense_shared.laser_region import LASER_REGION_POLYGON
    poly = np.array(LASER_REGION_POLYGON + LASER_REGION_POLYGON[:1], float)
    ax.plot(poly[:, 0], poly[:, 1], color=(0, 1, 0), linewidth=OUTLINE_PT, solid_joinstyle="round")
    if inset:
        import csv
        dot = next((float(r["laser_x"]), float(r["laser_y"])) for r in csv.DictReader(open(REPO / "e2e_measurement/tail/frames.csv"))
                   if int(r["image_id"]) == IMAGE_ID)
        half = 120
        x0, y0 = int(dot[0] - half), int(dot[1] - half)
        ia = ax.inset_axes([0.70, 0.02, 0.28, 0.28 * w / h])
        ia.imshow(img, interpolation="nearest")            # same image, zoomed by limits, so the connectors land right
        ia.set_xlim(x0, x0 + 2 * half); ia.set_ylim(y0 + 2 * half, y0); ia.set_xticks([]); ia.set_yticks([])
        for sp in ia.spines.values():
            sp.set_edgecolor("white"); sp.set_linewidth(1.2)
        from matplotlib.patches import ConnectionPatch
        x1, y1 = x0 + 2 * half, y0 + 2 * half
        ax.add_patch(plt.Rectangle((x0, y0), 2 * half, 2 * half, fill=False, edgecolor="white", linewidth=0.9))
        # corner to matching corner: the box's bottom-left to the inset's bottom-left, top-right to top-right,
        # so the two lines frame the zoom instead of crossing it (image y grows downward)
        for corner in ((x0, y1), (x1, y0)):
            fig.add_artist(ConnectionPatch(xyA=corner, coordsA=ax.transData, xyB=corner, coordsB=ia.transData,
                                           color="white", linewidth=0.8, alpha=0.9))
    fig.subplots_adjust(0, 0, 1, 1)
    name = "labeling_interface" + ("_inset" if inset else "")
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None}, dpi=300)
    fig.savefig(OUT / f"{name}.png", metadata={"Software": None}, dpi=300)
    plt.close(fig); print("wrote", name)


def main():
    OUT.mkdir(exist_ok=True)
    jpeg = production_jpeg()
    (OUT / "labeling_interface_full.jpg").write_bytes(jpeg)
    print(f"production JPEG: {len(jpeg):,} bytes")
    for inset in (False, True):
        figure(jpeg, inset)


if __name__ == "__main__":
    main()
