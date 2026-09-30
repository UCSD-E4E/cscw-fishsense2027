"""Coverage diagnostic, GPU pass: every SAM 3.1 mask down to 0.1 confidence, three prompts.

Production keeps masks above 0.5 for the prompt "fish" and requires the dot on a mask pixel.
To see why real reef frames fail (51 % mask coverage vs 92 % in the pool), this keeps every
mask above 0.1 for the prompts "fish", "reef fish" and "a fish" on the production 1800x1350
window at the HUMAN dot, with its score -> coverage/<id>.npz. The remedies (lower threshold,
dot tolerance, prompt ensemble, bigger window) are then scored on CPU (coverage.py) with the
production keypointer, against the human head/tail clicks -- so any extra mask has to be the
right fish, not just a mask.

Run from fishsense-lite's venv; loads SAM once and exits.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import run_e2e as E  # noqa: E402
from stage import STAGE  # noqa: E402

OUT = HERE / "coverage"
PROMPTS = ["fish", "reef fish", "a fish"]
FLOOR = 0.1


def _grounding_chunked(self, state):
    """sam3's Sam3Processor._forward_grounding, with the full-size mask upsampling done a few
    masks at a time. Same arithmetic and output per mask; production's version allocates every
    kept mask at full crop size at once, which at a 0.1 floor exceeds this shared 6 GB card."""
    import torch
    from torch.nn.functional import interpolate
    from sam3.model import box_ops
    with torch.inference_mode():
        out = self.model.forward_grounding(backbone_out=state["backbone_out"], find_input=self.find_stage,
                                           geometric_prompt=state["geometric_prompt"], find_target=None)
        probs = (out["pred_logits"].sigmoid() * out["presence_logit_dec"].sigmoid().unsqueeze(1)).squeeze(-1)
        keep = probs > self.confidence_threshold
        probs, low = probs[keep], out["pred_masks"][keep]
        h, w = state["original_height"], state["original_width"]
        masks = [(interpolate(low[i:i + 4].unsqueeze(1), (h, w), mode="bilinear", align_corners=False).sigmoid() > 0.5).cpu()
                 for i in range(0, len(low), 4)]
        state["masks"] = torch.cat(masks) if masks else torch.zeros(0, 1, h, w, dtype=torch.bool)
        state["scores"] = probs
        state["boxes"] = box_ops.box_cxcywh_to_xyxy(out["pred_boxes"][keep])
    return state


def main():
    import cv2, PIL.Image, torch
    from fishsense_data_processing_workflow_worker.activities.predict_headtail_image import _load_segmenter
    from fishsense_data_processing_workflow_worker.headtail_geometry import crop_origin
    from fishsense_shared.headtail_predictor import HEADTAIL_CROP_WIDTH as CW, HEADTAIL_CROP_HEIGHT as CH
    OUT.mkdir(exist_ok=True)
    F = pd.read_csv(HERE / "frames.csv"); F = F[F.set == "reef"]
    F = F[[(STAGE / f"{i}.jpg").exists() and not (OUT / f"{i}.npz").exists() for i in F.image_id]]
    print(f"{len(F)} reef frames; cuda {torch.cuda.is_available()}", flush=True)
    import types
    proc = _load_segmenter(E.SAM3_CKPT); proc._forward_grounding = types.MethodType(_grounding_chunked, proc)
    proc.set_confidence_threshold(FLOOR)
    for n, r in enumerate(F.itertuples(), 1):
        img = cv2.imread(str(STAGE / f"{r.image_id}.jpg")); H, W = img.shape[:2]
        ox, oy = crop_origin(r.laser_x, r.laser_y, W, H, CW, CH)
        pil = PIL.Image.fromarray(cv2.cvtColor(np.ascontiguousarray(img[oy:oy + CH, ox:ox + CW]), cv2.COLOR_BGR2RGB))
        rec = dict(origin=np.array([ox, oy]))
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            state = proc.set_image(pil)
            for k, prompt in enumerate(PROMPTS):
                st = proc.set_text_prompt(prompt, state)
                ms = st.get("masks"); sc = st.get("scores")
                if ms is None or len(ms) == 0:
                    rec[f"p{k}_scores"] = np.zeros(0); continue
                ms = ms.squeeze(1).cpu().numpy().astype(bool); sc = sc.float().cpu().numpy()
                rec[f"p{k}_scores"] = sc
                rec[f"p{k}_masks"] = np.packbits(ms.reshape(len(ms), -1), axis=1)
        del state, st; torch.cuda.empty_cache()
        rec["shape"] = np.array([CH, CW]); rec["floor"] = FLOOR
        np.savez_compressed(OUT / f"{r.image_id}.npz", **rec)
        if n % 100 == 0:
            print(f"{n}/{len(F)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
