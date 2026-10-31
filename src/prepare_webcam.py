"""Your corrected photos -> YOLO dataset split BY MEAL + data.yaml for fine-tuning.

    python src/prepare_webcam.py
    python src/train.py --data data/processed/webcam_yolo/data.yaml \
        --model runs/combined_s/weights/best.pt --epochs 60 --flipud 0.5 --name webcam_s

Takes photos that have a .json file (outlines from X-AnyLabeling). Training also includes FoodSeg103 and
Food-101 so the model doesn't forget the rest, and your photos are repeated --repeat times (few, but the most
important ones).
"""
import argparse
import json
import random
import shutil
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def to_yolo(js: dict, cls_id: dict) -> tuple[list[str], list[str]]:
    w, h = js["imageWidth"], js["imageHeight"]
    lines, unknown = [], []
    for s in js["shapes"]:
        if s["label"] not in cls_id:
            unknown.append(s["label"])
            continue
        if s.get("shape_type", "polygon") != "polygon" or len(s["points"]) < 3:
            continue
        xy = " ".join(f"{min(max(x / w, 0), 1):.5f} {min(max(y / h, 0), 1):.5f}" for x, y in s["points"])
        lines.append(f"{cls_id[s['label']]} {xy}")
    return lines, unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT / "data/webcam/raw")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/webcam_yolo")
    ap.add_argument("--split", type=float, nargs=3, default=(0.7, 0.15, 0.15), help="train val test (by meal)")
    ap.add_argument("--repeat", type=int, default=3, help="how many times to repeat your photos in training")
    args = ap.parse_args()

    classes = yaml.safe_load((ROOT / "configs/classes.yaml").read_text(encoding="utf-8"))["classes"]
    cls_id = {c["name"]: i for i, c in enumerate(classes)}
    meals = sorted(d for d in args.root.iterdir() if d.is_dir() and any(p.name != "meta.json" for p in d.glob("*.json")))
    if len(meals) < 3:
        raise SystemExit(f"Too few labeled meals ({len(meals)}). Need at least a few — ideally 30+.")

    random.Random(0).shuffle(meals)
    n_va = max(1, round(len(meals) * args.split[1]))
    n_te = max(1, round(len(meals) * args.split[2]))
    n_tr = len(meals) - n_va - n_te
    split_of = {m: "train" if i < n_tr else "val" if i < n_tr + n_va else "test" for i, m in enumerate(meals)}

    if args.out.exists():
        shutil.rmtree(args.out)
    counts, n_img, unknown = {s: Counter() for s in ("train", "val", "test")}, Counter(), Counter()
    for meal, split in split_of.items():
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)
        for js_path in sorted(meal.glob("*.json")):
            if js_path.name == "meta.json":
                continue
            img = js_path.with_suffix(".jpg")
            if not img.exists():
                continue
            lines, unk = to_yolo(json.loads(js_path.read_text(encoding="utf-8")), cls_id)
            unknown.update(unk)
            stem = f"{meal.name}_{img.stem}"
            shutil.copy(img, args.out / "images" / split / f"{stem}.jpg")
            (args.out / "labels" / split / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
            n_img[split] += 1
            counts[split].update(classes[int(l.split(' ', 1)[0])]["name"] for l in lines)

    processed = ROOT / "data/processed"
    general = [processed / "foodseg_yolo/images/train", processed / "food101_pseudo/images/train"]
    data = {
        "path": str(args.out),
        "train": [str(args.out / "images/train")] * args.repeat + [str(p) for p in general if p.exists()],
        "val": str(args.out / "images/val"),
        "test": str(args.out / "images/test"),
        "names": {i: c["name"] for i, c in enumerate(classes)},
    }
    (args.out / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"Meals: {Counter(split_of.values())}, photos: {dict(n_img)}")
    for name in cls_id:
        if any(counts[s][name] for s in counts):
            print(f"  {name:<20} train {counts['train'][name]:>4}  val {counts['val'][name]:>4}  test {counts['test'][name]:>4}")
    if unknown:
        print(f"WARNING, unknown labels (skipped — fix the names in X-AnyLabeling): {dict(unknown)}")
    print(f"Done: {args.out / 'data.yaml'}")


if __name__ == "__main__":
    main()
