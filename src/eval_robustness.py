"""Webcam robustness test + A/B experiment with image enhancement models.

1. Test set -> a "webcam-like" copy (fixed simulation: noise, blur, warm light, JPEG).
2. That copy passed through enhancement models:
     scunet  — SCUNet (denoising of real camera photos)
     esrgan  — Real-ESRGAN x2 (super-resolution), then back to the input size
3. Mask mAP for every variant.

    python src/eval_robustness.py --weights runs/foodseg_s/weights/best.pt --data data/processed/combined.yaml
    python src/eval_robustness.py --prepare-only    # only prepare the images (no trained model needed)
"""
import argparse
import json
import shutil
from pathlib import Path

import albumentations as A
import cv2
import torch
import yaml
from tqdm import tqdm

from enhance import ENHANCERS, Enhancer

ROOT = Path(__file__).resolve().parents[1]


def webcam_sim(seed: int = 0) -> A.Compose:
    """Fixed, realistic degradation — every component always on, strength drawn from a narrow range."""
    return A.Compose([
        A.Downscale(scale_range=(0.55, 0.7), p=1),
        A.GaussianBlur(blur_limit=(3, 5), sigma_limit=(0.6, 1.2), p=1),
        A.ISONoise(color_shift=(0.02, 0.04), intensity=(0.15, 0.35), p=1),
        A.GaussNoise(std_range=(0.02, 0.04), p=1),
        A.RandomBrightnessContrast(brightness_limit=(-0.25, -0.1), contrast_limit=(-0.2, -0.05), p=1),
        A.PlanckianJitter(mode="blackbody", temperature_limit=(3000, 6000), p=1),
        A.ImageCompression(quality_range=(40, 65), p=1),
    ], seed=seed)


def test_images(data_yaml: Path) -> list[Path]:
    d = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    dirs = d["test"] if isinstance(d["test"], list) else [d["test"]]
    base = Path(d.get("path", data_yaml.parent))
    return [p for t in dirs for p in sorted((base / t).glob("*.jpg"))]


def label_for(img: Path) -> Path:
    return img.parents[2] / "labels" / img.parent.name / f"{img.stem}.txt"


def write_variant(name: str, images: list[Path], fn, out_root: Path) -> Path:
    vdir = out_root / name
    if (vdir / "data.yaml").exists():
        return vdir / "data.yaml"
    (vdir / "images/test").mkdir(parents=True, exist_ok=True)
    (vdir / "labels/test").mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(tqdm(images, desc=name)):
        stem = f"{i:05d}_{p.stem}"
        cv2.imwrite(str(vdir / "images/test" / f"{stem}.jpg"), fn(p), [cv2.IMWRITE_JPEG_QUALITY, 95])
        shutil.copy(label_for(p), vdir / "labels/test" / f"{stem}.txt")
    return vdir / "data.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, default=ROOT / "runs/foodseg_s/weights/best.pt")
    ap.add_argument("--data", type=Path, default=ROOT / "data/processed/foodseg_yolo/data.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/robustness")
    ap.add_argument("--variants", default="clean,webcam,scunet,esrgan")
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()

    names = yaml.safe_load(args.data.read_text(encoding="utf-8"))["names"]
    images = test_images(args.data)
    out_root = args.out / (args.data.parent.name if args.data.stem == "data" else args.data.stem)
    sim = webcam_sim()
    webcam_dir = out_root / "webcam/images/test"

    yamls = {}
    for v in args.variants.split(","):
        if v == "clean":
            fn = lambda p: cv2.imread(str(p))
        elif v == "webcam":
            fn = lambda p: sim(image=cv2.imread(str(p)))["image"]
        else:  # enhancer applied to the "webcam" images (must exist already)
            enh = Enhancer(ENHANCERS[v])
            webcam_imgs = sorted(webcam_dir.glob("*.jpg"))
            assert len(webcam_imgs) == len(images), "prepare the webcam variant first"
            src = dict(zip(images, webcam_imgs))
            fn = lambda p, enh=enh, src=src: enh(cv2.imread(str(src[p])))
        y = write_variant(v, images, fn, out_root)
        y.write_text(yaml.safe_dump({"path": str(y.parent), "train": "images/test", "val": "images/test", "test": "images/test",
                                     "names": names}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        yamls[v] = y
        torch.cuda.empty_cache()

    if args.prepare_only:
        return

    from ultralytics import YOLO
    model = YOLO(args.weights)
    results = {}
    for v, y in yamls.items():
        m = model.val(data=str(y), split="test", imgsz=640, batch=16, verbose=False, plots=False,
                      project=str(ROOT / "runs"), name=f"robust_{v}", exist_ok=True)
        results[v] = {"mask_mAP50": round(m.seg.map50, 4), "mask_mAP50_95": round(m.seg.map, 4),
                      "box_mAP50": round(m.box.map50, 4),
                      "per_class_mask_mAP50_95": {names[int(c)]: round(float(a), 4)
                                                   for c, a in zip(m.seg.ap_class_index, m.seg.ap)}}

    report = ROOT / "runs" / f"robustness_{args.weights.parent.parent.name}_{out_root.name}.json"
    report.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'variant':<10}{'mask mAP50':>12}{'mask mAP50-95':>15}{'box mAP50':>11}")
    for v, r in results.items():
        print(f"{v:<10}{r['mask_mAP50']:>12.3f}{r['mask_mAP50_95']:>15.3f}{r['box_mAP50']:>11.3f}")
    print(f"\nDetails: {report}")


if __name__ == "__main__":
    main()
