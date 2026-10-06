"""Apparent slate size from SAM 3.1 masks, two ways, for the tape comparison (tape_by_session.py).

  sam3_box   mask prompted with the human-labelled slate rectangle (diveslatelabel.slate_rectangle);
             the highest-scoring mask, sqrt(area)
  sam3_text  text prompt "slate" (then "white board" if nothing covers the dot); the highest-scoring
             mask containing the laser dot, sqrt(area); uses no labels

Frames: the 258 slate frames of the 10 calibration sessions (sizes_frames.csv), from the slate
detector's render cache (rectified, 1600x1202; dot and rectangle scaled by 1600/4014). Only size
ratios within a session matter, so render-scale pixels are fine. One short GPU pass.

Writes sizes/sam3_box.csv, sizes/sam3_text.csv (image_id,size) and sam_sizes_detail.csv.
Run from fishsense-lite's venv (see e2e_measurement/run_e2e.py for the environment).
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "e2e_measurement"))
import run_e2e as E  # noqa: E402

FRAMES = REPO.parent / "2026-10-03_slate_detector" / "data" / "frames"
SCALE = 1600 / 4014
PROMPTS = ("slate", "white board")
import glob, os
# production runs SAM 3.1 (sam3.1_multiplex.pt); fall back to the local SAM 3 v1 checkpoint if 3.1 is not on disk
SAM3_CKPT = os.environ.get("SAM3_CKPT") or (E.SAM3_CKPT if Path(E.SAM3_CKPT).exists() else
    glob.glob(str(REPO.parent / "coral-gardeners-fish-detector/models/hf_cache/hub/models--facebook--sam3/snapshots/*/sam3.pt"))[0])


def main(rects_path):
    import PIL.Image, torch
    from fishsense_data_processing_workflow_worker.activities.predict_headtail_image import _load_segmenter
    F = pd.read_csv(HERE / "sizes_frames.csv")
    R = pd.read_csv(rects_path, sep="|", header=None, names=["image_id", "rect", "pts"]).drop_duplicates("image_id").set_index("image_id")
    print('checkpoint:', SAM3_CKPT, flush=True)
    proc = _load_segmenter(SAM3_CKPT); proc.set_confidence_threshold(0.3)
    rows = []
    for n, r in enumerate(F.itertuples(), 1):
        img = PIL.Image.open(FRAMES / f"{r.image_id}.jpg").convert("RGB"); W, H = img.size
        x, y = int(round(r.dot_x * SCALE)), int(round(r.dot_y * SCALE))
        rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id))
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            state = proc.set_image(img)
            for prompt in PROMPTS:                                   # text: the mask under the dot
                st = proc.set_text_prompt(prompt, state)
                ms, sc = st.get("masks"), st.get("scores")
                if ms is None or len(ms) == 0:
                    continue
                ms = ms.squeeze(1).cpu().numpy(); sc = sc.float().cpu().numpy()
                hit = [i for i in range(len(ms)) if 0 <= y < H and 0 <= x < W and ms[i][y, x]]
                if hit:
                    i = max(hit, key=lambda k: sc[k])
                    rec.update(text_prompt=prompt, text_score=float(sc[i]), text_area=int(ms[i].sum()))
                    break
            if r.image_id in R.index and isinstance(R.loc[r.image_id, "rect"], str):
                (x0, y0), (x1, y1) = np.array(json.loads(R.loc[r.image_id, "rect"])) * SCALE
                box = [((x0 + x1) / 2) / W, ((y0 + y1) / 2) / H, abs(x1 - x0) / W, abs(y1 - y0) / H]
                proc.reset_all_prompts(state)
                st = proc.add_geometric_prompt(box, True, state)
                ms, sc = st.get("masks"), st.get("scores")
                if ms is not None and len(ms):
                    i = int(sc.float().argmax()); m = ms[i].squeeze(0).cpu().numpy()
                    rec.update(box_score=float(sc[i]), box_area=int(m.sum()), box_rect_area=float(abs(x1 - x0) * abs(y1 - y0)),
                               box_has_dot=bool(0 <= y < H and 0 <= x < W and m[y, x]))
        del state; torch.cuda.empty_cache()
        rows.append(rec)
        if n % 50 == 0:
            print(f"{n}/{len(F)}", flush=True)
    D = pd.DataFrame(rows); D.to_csv(HERE / "sam_sizes_detail.csv", index=False)
    (HERE / "sizes").mkdir(exist_ok=True)
    for col, name in (("box_area", "sam3_box"), ("text_area", "sam3_text")):
        z = D.dropna(subset=[col])
        pd.DataFrame(dict(image_id=z.image_id, size=np.sqrt(z[col]))).to_csv(HERE / "sizes" / f"{name}.csv", index=False)
        print(f"{name}: {len(z)} of {len(D)} frames")
    print("text prompt used:", D.text_prompt.value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    main(sys.argv[1])
