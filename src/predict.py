"""Recognize food components on a plate + estimate grams, kcal and macros.

    python src/predict.py --source 0              # photo from webcam 0
    python src/predict.py --source plate.jpg      # photo from disk

Scale (px/cm) comes from configs/camera.yaml (python src/calibrate.py) or --px-per-cm.
Nutrients and g/cm² factors: configs/nutrition.yaml.
"""
import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

from camera import grab_sharpest, open_camera
from seg_utils import instances

ROOT = Path(__file__).resolve().parents[1]


def default_weights() -> Path:
    """Newest trained model: final > webcam_s (fine-tuned on your photos) > combined_v2 (30 classes) > combined_s > foodseg_s."""
    for name in ("final", "webcam_s", "combined_v2", "combined_s", "foodseg_s"):
        p = ROOT / "runs" / name / "weights/best.pt"
        if p.exists():
            return p
    raise SystemExit("No trained model in runs/*/weights/best.pt")


def load_px_per_cm(override: float | None, img_w: int) -> float | None:
    if override:
        return override
    cfg_path = ROOT / "configs/camera.yaml"
    if not cfg_path.exists():
        return None
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return cfg["px_per_cm"] * img_w / cfg["width"]  # different resolution than at calibration time


def estimate(result, nutrition: dict, px_per_cm: float | None) -> dict:
    return estimate_items([(n, c, a) for n, c, a, _ in instances(result)], nutrition, px_per_cm)


def estimate_items(detections: list[tuple[str, float, float]], nutrition: dict, px_per_cm: float | None) -> dict:
    """(class, confidence, area in px) per detected item -> per class: count, confidence, cm², g, kcal, macros."""
    items = defaultdict(lambda: {"count": 0, "px": 0.0, "conf": []})
    for name, conf, area_px in detections:
        it = items[name]
        it["count"] += 1
        it["px"] += area_px
        it["conf"].append(conf)

    out = {}
    for name, it in items.items():
        row = {"count": it["count"], "confidence": float(np.mean(it["conf"]))}
        if px_per_cm:
            n = nutrition[name]
            cm2 = it["px"] / px_per_cm**2
            g = cm2 * n["g_cm2"]
            row |= {"cm2": cm2, "g": g, "kcal": g * n["kcal"] / 100, "protein": g * n["protein"] / 100,
                    "fat": g * n["fat"] / 100, "carbs": g * n["carbs"] / 100, "uncertainty": n["uncertainty"]}
        out[name] = row
    return out


def print_table(est: dict, calibrated: bool):
    if not est:
        print("Nothing recognized.")
        return
    if not calibrated:
        print("No scale calibration (python src/calibrate.py) — showing components only.\n")
        for name, r in est.items():
            print(f"  {name:<20} x{r['count']}  confidence {r['confidence']:.2f}")
        return

    print(f"{'item':<20}{'n':>4}{'cm²':>7}{'g':>6}{'kcal':>14}{'P':>6}{'F':>6}{'C':>6}{'conf':>7}")
    tot = defaultdict(float)
    for name, r in sorted(est.items(), key=lambda kv: -kv[1]["kcal"]):
        lo, hi = r["kcal"] * (1 - r["uncertainty"]), r["kcal"] * (1 + r["uncertainty"])
        print(f"{name:<20}{r['count']:>4}{r['cm2']:>7.0f}{r['g']:>6.0f}{r['kcal']:>6.0f} ({lo:.0f}-{hi:.0f})"
              f"{r['protein']:>6.1f}{r['fat']:>6.1f}{r['carbs']:>6.1f}{r['confidence']:>7.2f}")
        for k, v in (("kcal", r["kcal"]), ("lo", lo), ("hi", hi), ("g", r["g"]),
                     ("protein", r["protein"]), ("fat", r["fat"]), ("carbs", r["carbs"])):
            tot[k] += v
    print("-" * 76)
    print(f"{'TOTAL':<31}{tot['g']:>6.0f}{tot['kcal']:>6.0f} ({tot['lo']:.0f}-{tot['hi']:.0f})"
          f"{tot['protein']:>6.1f}{tot['fat']:>6.1f}{tot['carbs']:>6.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0", help="camera index or image path")
    ap.add_argument("--weights", type=Path)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--px-per-cm", type=float)
    ap.add_argument("--denoise", choices=["none", "scunet", "esrgan"], default="none",
                    help="experimental: enhance the photo before recognition (src/enhance.py)")
    ap.add_argument("--show", action="store_true", help="show a window with the result")
    args = ap.parse_args()

    if args.source.isdigit():
        cap = open_camera(int(args.source))
        img = grab_sharpest(cap)
        cap.release()
    else:
        img = cv2.imread(args.source)
        if img is None:
            raise SystemExit(f"Cannot read {args.source}")

    if args.denoise != "none":
        from enhance import ENHANCERS, Enhancer
        img = Enhancer(ENHANCERS[args.denoise])(img)

    nutrition = yaml.safe_load((ROOT / "configs/nutrition.yaml").read_text(encoding="utf-8"))
    model = YOLO(args.weights or default_weights())
    result = model(img, conf=args.conf, imgsz=args.imgsz, retina_masks=True, verbose=False)[0]
    px_per_cm = load_px_per_cm(args.px_per_cm, img.shape[1])
    print_table(estimate(result, nutrition, px_per_cm), calibrated=px_per_cm is not None)

    out_dir = ROOT / "runs/predict"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    cv2.imwrite(str(out_dir / f"{stamp}.jpg"), img)
    cv2.imwrite(str(out_dir / f"{stamp}_result.jpg"), result.plot())
    print(f"\nSaved: {out_dir / (stamp + '_result.jpg')}")
    if args.show:
        cv2.imshow("result", result.plot())
        cv2.waitKey(0)


if __name__ == "__main__":
    main()
