"""Food-101 pseudo-labels for classes missing from FoodSeg103 (toast) or rare there (pizza, pasta).

The dish class comes from the Food-101 label (reliable); the outline is drawn by YOLOE-26 (a text-promptable
model). Confidently detected sides (fries, salad, sauce, bread, vegetables) are labeled too, so the model
isn't taught that they are background.

    python -I src/autolabel_food101.py             # -> data/processed/food101_pseudo + data/processed/combined.yaml
    python -I src/autolabel_food101.py --preview   # 12 images per class to runs/food101_preview (for checking)
"""
import argparse
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm
from ultralytics import YOLOE

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I does not add the script directory
from seg_utils import instances  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Food-101 label -> (our class, YOLOE prompt)
SELECT = {
    "pizza": ("pizza", "pizza"),
    "grilled_cheese_sandwich": ("toast", "toasted sandwich"),
    "spaghetti_bolognese": ("pasta", "pasta with sauce"),  # "spaghetti"/"pasta" are found 2x less often by YOLOE
    "spaghetti_carbonara": ("pasta", "pasta with sauce"),
    "macaroni_and_cheese": ("pasta", "pasta with sauce"),
    # added 2026-10-13 (labeled into food101_pseudo_v2, see the README)
    "hamburger": ("burger", "hamburger"),
    "hot_dog": ("hot_dog", "hot dog"),
    "breakfast_burrito": ("burrito", "tortilla wrap"),   # "burrito" was found in 5/12 photos, this in 9/12
    "dumplings": ("dumplings", "dumplings"),
    "gyoza": ("dumplings", "fried dumplings"),           # "dumplings" found 5/12 pan-fried gyoza, this 7/12
}
# sides: prompt -> our class (kept only at high confidence)
EXTRAS = {"french fries": "fries", "salad": "salad", "sauce": "sauce", "bread": "bread", "vegetables": "vegetables"}
# prompts that only "absorb" pixels, so the dish outline does not spill onto the plate/cutlery
DISTRACTORS = ["plate", "bowl", "fork", "knife", "napkin", "table", "pickle"]
# sides not asked for a given dish (sauce is part of pizza and pasta-with-sauce, toast is bread)
SKIP_EXTRAS = {"pizza": {"sauce", "bread"}, "toast": {"bread"}, "pasta": {"sauce"},
               "burger": {"bread", "salad", "vegetables"},     # bun, lettuce and tomato are part of the burger
               "hot_dog": {"bread", "sauce"}, "burrito": {"bread", "vegetables"}}

PER_CLASS = {"train": 600, "val": 60, "test": 120}  # per our class, split across Food-101 labels


def food101_names(readme: Path) -> list[str]:
    """Class names from the dataset card (class_label names section: '0': apple_pie ...)."""
    text = readme.read_text(encoding="utf-8")
    pairs = re.findall(r"'(\d+)':\s*([a-z_]+)", text)
    names = [n for _, n in sorted(pairs, key=lambda p: int(p[0]))]
    assert len(names) == 101, f"Could not read 101 classes from {readme} ({len(names)})"
    return names


def collect(files: list[Path], wanted: dict[int, int], seed: int) -> dict[int, list[bytes]]:
    """Collects JPEG bytes for the wanted labels (shuffled)."""
    pool = defaultdict(list)
    for f in files:
        for batch in pq.ParquetFile(f).iter_batches(batch_size=512, columns=["image", "label"]):
            labels = batch.column("label").to_pylist()
            images = batch.column("image")
            for i, lab in enumerate(labels):
                if lab in wanted:
                    pool[lab].append(images[i].as_py()["bytes"])
    rng = random.Random(seed)
    for lab in pool:
        rng.shuffle(pool[lab])
    return pool


def polygons(result, keep: dict[str, tuple[int, float]], min_area: float, main_name: str) -> list[str]:
    """Outlines of detections whose name is in `keep` (name -> (class id, confidence threshold)).

    For the main dish the threshold is also relative (half of the best score in the image) — this cuts
    single mistakes, e.g. a pickle taken for a toast next to a real toast.
    """
    inst = instances(result, min_area)
    h, w = result.orig_shape
    top = max((c for n, c, _, _ in inst if n == main_name), default=0)
    lines = []
    for name, conf, _, polys in inst:
        if name not in keep or conf < keep[name][1] or (name == main_name and conf < 0.5 * top):
            continue
        for poly in polys:
            xy = (poly / np.array([w, h])).clip(0, 1).ravel()
            lines.append(f"{keep[name][0]} " + " ".join(f"{v:.5f}" for v in xy))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data/raw/food101")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/food101_pseudo")
    ap.add_argument("--model", default=str(ROOT / "models/yoloe-26l-seg.pt"))
    ap.add_argument("--conf", type=float, default=0.25, help="threshold for the main dish")
    ap.add_argument("--extra-conf", type=float, default=0.5, help="threshold for sides")
    ap.add_argument("--min-area", type=float, default=0.002)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--labels", help="only these Food-101 labels (comma-separated), e.g. for newly added classes")
    ap.add_argument("--foodseg", type=Path, default=ROOT / "data/processed/foodseg_yolo")
    ap.add_argument("--combined", type=Path, default=ROOT / "data/processed/combined.yaml")
    ap.add_argument("--extra-sets", type=Path, nargs="*", default=[],
                    help="earlier pseudo-label folders to include in the combined dataset")
    ap.add_argument("--fill", action="store_true", help="replace photos where YOLOE finds no dish with further ones")
    args = ap.parse_args()
    if args.preview:
        args.out = ROOT / "runs/food101_preview"
    select = {k: v for k, v in SELECT.items() if not args.labels or k in args.labels.split(",")}

    names = yaml.safe_load((ROOT / "configs/classes.yaml").read_text(encoding="utf-8"))["classes"]
    cls_id = {c["name"]: i for i, c in enumerate(names)}
    f101 = food101_names(args.raw / "README.md")
    by_target = defaultdict(list)
    for lab, (target, _) in select.items():
        by_target[target].append(lab)

    model = YOLOE(args.model)
    stats = defaultdict(lambda: defaultdict(int))

    for split, files in (("train", sorted((args.raw / "data").glob("train-*.parquet"))),
                         ("valtest", sorted((args.raw / "data").glob("validation-*.parquet")))):
        limit = {lab: (PER_CLASS["train"] if split == "train" else PER_CLASS["val"] + PER_CLASS["test"])
                 // len(by_target[t]) for lab, (t, _) in select.items()}
        wanted = {f101.index(lab): lab for lab in select}
        pool = collect(files, wanted, seed=0)

        for lab_idx, lab in wanted.items():
            target, prompt = select[lab]
            extras = {p: c for p, c in EXTRAS.items() if p not in SKIP_EXTRAS.get(target, set())}
            prompts = [prompt] + list(extras) + DISTRACTORS
            model.set_classes(prompts)
            keep = {prompt: (cls_id[target], args.conf)} | {p: (cls_id[c], args.extra_conf) for p, c in extras.items()}

            # with --fill, photos where YOLOE finds nothing are replaced by further ones until the quota is met
            want = 12 if args.preview else limit[lab]
            imgs = pool[lab_idx] if args.fill and not args.preview else pool[lab_idx][:want]
            kept = 0
            for k, img_bytes in enumerate(tqdm(imgs, desc=f"{split}:{lab}")):
                if kept >= want:
                    break
                if split == "train":
                    sub = "train"
                else:
                    n_val = PER_CLASS["val"] // len(by_target[target])
                    sub = "val" if (kept if args.fill else k) < n_val else "test"
                img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
                res = model.predict(img, conf=0.1, imgsz=640, retina_masks=True, verbose=False)[0]
                lines = polygons(res, keep, args.min_area, prompt)
                main_cls = cls_id[target]
                if not any(int(l.split(" ", 1)[0]) == main_cls for l in lines):
                    stats[lab]["skipped"] += 1  # YOLOE did not find the dish — no guessing
                    continue
                stem = f"{lab}_{split}_{k:04d}"
                (args.out / "images" / sub).mkdir(parents=True, exist_ok=True)
                (args.out / "labels" / sub).mkdir(parents=True, exist_ok=True)
                (args.out / "images" / sub / f"{stem}.jpg").write_bytes(img_bytes)
                (args.out / "labels" / sub / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
                stats[lab][sub] += 1
                kept += 1
        if args.preview:
            break

    print("\nResult (images per split, skipped = YOLOE did not find the dish):")
    for lab, s in stats.items():
        print(f"  {lab:<26} {dict(s)}")

    sets = [d.resolve() for d in (args.foodseg, *args.extra_sets, args.out)]
    combined = {
        "path": str(ROOT / "data/processed"),
        **{s: [str(d / "images" / s) for d in sets] for s in ("train", "val", "test")},
        "names": {i: c["name"] for i, c in enumerate(names)},
    }
    if not args.preview:
        out_yaml = args.combined
        out_yaml.write_text(yaml.safe_dump(combined, allow_unicode=True, sort_keys=False), encoding="utf-8")
        own = {"path": str(args.out), "train": "images/train", "val": "images/val", "test": "images/test",
               "names": combined["names"]}
        (args.out / "data.yaml").write_text(yaml.safe_dump(own, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"Combined dataset: {out_yaml}")


if __name__ == "__main__":
    main()
