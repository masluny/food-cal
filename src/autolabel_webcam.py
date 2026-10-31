"""Pre-labels for your webcam photos — to be corrected in X-AnyLabeling.

    python src/autolabel_webcam.py

For every data/webcam/raw/<meal>/*.jpg without a .json file it writes <photo>.json next to it
(LabelMe format, which X-AnyLabeling opens automatically). Existing .json files are never overwritten,
so your corrections are safe. Toasts are additionally searched for by YOLOE; outline zapiekanka by hand.

Then: X-AnyLabeling -> Open Dir -> meal folder -> fix outlines/classes -> Ctrl+S.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO, YOLOE

from predict import default_weights
from seg_utils import instances

ROOT = Path(__file__).resolve().parents[1]
# Toasts only: "toasted sandwich" worked on Food-101. YOLOE confuses zapiekanka with roast meat
# (test 2026-10-12), so outline those by hand — SAM in X-AnyLabeling does it in one click.
YOLOE_PROMPTS = {"toasted sandwich": "toast"}
# filler prompts: without them YOLOE assigns every food to the class above
YOLOE_DISTRACTORS = ["food", "vegetables", "meat", "chicken", "rice", "pasta", "bread", "fruit", "potato",
                     "plate", "bowl"]
REPLACEABLE = {"bread", "toast", "zapiekanka", "pizza"}  # classes YOLOE may override


def shapes_from(result, conf: float, rename: dict | None = None) -> list[dict]:
    out = []
    for name, c, _, polys in instances(result, min_area_frac=0.002, eps_frac=0.003):
        if c < conf or (rename is not None and name not in rename):
            continue
        for poly in polys:
            out.append({"label": rename.get(name, name) if rename else name, "points": poly.round(1).tolist(),
                        "shape_type": "polygon", "flags": {}, "description": f"auto {c:.2f}"})
    return out


def box_iou(a: list, b: list) -> float:
    (ax0, ay0), (ax1, ay1) = np.min(a, 0), np.max(a, 0)
    (bx0, by0), (bx1, by1) = np.min(b, 0), np.max(b, 0)
    iw, ih = max(0, min(ax1, bx1) - max(ax0, bx0)), max(0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    return inter / ((ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT / "data/webcam/raw")
    ap.add_argument("--weights", type=Path)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--yoloe-conf", type=float, default=0.5)
    ap.add_argument("--no-yoloe", action="store_true")
    args = ap.parse_args()

    names = [c["name"] for c in yaml.safe_load((ROOT / "configs/classes.yaml").read_text(encoding="utf-8"))["classes"]]
    (args.root / "classes.txt").write_text("\n".join(names), encoding="utf-8")

    model = YOLO(args.weights or default_weights())
    yoloe = None
    if not args.no_yoloe:
        yoloe = YOLOE(ROOT / "models/yoloe-26l-seg.pt")
        yoloe.set_classes(list(YOLOE_PROMPTS) + YOLOE_DISTRACTORS)

    todo = [p for p in sorted(args.root.glob("*/*.jpg")) if not p.with_suffix(".json").exists()]
    print(f"Photos to pre-label: {len(todo)}")
    for p in todo:
        img = cv2.imread(str(p))
        shapes = shapes_from(model(img, conf=args.conf, imgsz=640, retina_masks=True, verbose=False)[0], args.conf)
        if yoloe is not None:
            for s in shapes_from(yoloe(img, conf=args.yoloe_conf, imgsz=640, retina_masks=True, verbose=False)[0],
                                 args.yoloe_conf, YOLOE_PROMPTS):
                shapes = [o for o in shapes if not (o["label"] in REPLACEABLE and box_iou(o["points"], s["points"]) > 0.5)]
                shapes.append(s)
        p.with_suffix(".json").write_text(json.dumps({
            "version": "2.4.0", "flags": {}, "shapes": shapes, "imagePath": p.name, "imageData": None,
            "imageHeight": img.shape[0], "imageWidth": img.shape[1]}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  {p.parent.name}/{p.name}: {', '.join(s['label'] for s in shapes) or '—'}")
    print(f"\nClass list for X-AnyLabeling: {args.root / 'classes.txt'}")


if __name__ == "__main__":
    main()
