"""Convert FoodSeg103 (Hugging Face parquet) to YOLO-seg format with our classes.

Semantic masks -> instance polygons (connected regions of a class).
The FoodSeg103 -> our class mapping lives in configs/classes.yaml.

Run:  python -I src/prepare_foodseg.py
"""
import argparse
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]


def build_lut(classes_cfg: Path) -> tuple[np.ndarray, list[str]]:
    """Table 256 -> our class id (-1 = background / unmapped)."""
    cfg = yaml.safe_load(classes_cfg.read_text(encoding="utf-8"))
    names = [c["name"] for c in cfg["classes"]]
    lut = np.full(256, -1, dtype=np.int16)
    for cls_id, c in enumerate(cfg["classes"]):
        for fs_id in c["foodseg"]:
            if lut[fs_id] != -1:
                raise ValueError(f"FoodSeg id {fs_id} mapped twice ({names[lut[fs_id]]}, {c['name']})")
            lut[fs_id] = cls_id
    missing = [i for i in range(1, 104) if lut[i] == -1]
    if missing:
        raise ValueError(f"Unmapped FoodSeg103 classes: {missing}")
    return lut, names


def mask_to_polygons(cls_mask: np.ndarray, n_classes: int, min_area: float) -> list[str]:
    h, w = cls_mask.shape
    lines = []
    for cls_id in range(n_classes):
        binary = (cls_mask == cls_id).astype(np.uint8)
        if not binary.any():
            continue
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) < min_area * h * w:
                continue
            cnt = cv2.approxPolyDP(cnt, 0.002 * cv2.arcLength(cnt, True), True).reshape(-1, 2)
            if len(cnt) < 3:
                continue
            xy = (cnt / np.array([w, h])).clip(0, 1).ravel()
            lines.append(f"{cls_id} " + " ".join(f"{v:.5f}" for v in xy))
    return lines


def process(job: tuple) -> dict:
    img_bytes, lbl_bytes, stem, split, out, lut, n_classes, max_side, min_area = job
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    lbl = cv2.imdecode(np.frombuffer(lbl_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if lbl.ndim == 3:
        lbl = lbl[..., 0]
    if lbl.shape != img.shape[:2]:
        lbl = cv2.resize(lbl, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)

    scale = max_side / max(img.shape[:2])
    if scale < 1:
        size = (round(img.shape[1] * scale), round(img.shape[0] * scale))
        img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        lbl = cv2.resize(lbl, size, interpolation=cv2.INTER_NEAREST)

    lines = mask_to_polygons(lut[lbl], n_classes, min_area)
    cv2.imwrite(str(out / "images" / split / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    (out / "labels" / split / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
    counts = [0] * n_classes
    for line in lines:
        counts[int(line.split(" ", 1)[0])] += 1
    return {"split": split, "counts": counts}


def iter_rows(files: list[Path]):
    for f in files:
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=64, columns=["image", "label", "id"]):
            for row in batch.to_pylist():
                yield row["image"]["bytes"], row["label"]["bytes"], row["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data/raw/foodseg103/data")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/foodseg_yolo")
    ap.add_argument("--classes", type=Path, default=ROOT / "configs/classes.yaml")
    ap.add_argument("--max-side", type=int, default=800, help="longer side of the saved images")
    ap.add_argument("--val-count", type=int, default=700, help="the rest of the official validation goes to test")
    ap.add_argument("--min-area", type=float, default=0.0005, help="min instance area as a fraction of the image")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    lut, names = build_lut(args.classes)
    for split in ("train", "val", "test"):
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)

    # official validation -> val (to pick the best epoch) + test (final evaluation)
    val_files = sorted(args.raw.glob("validation-*.parquet"))
    val_ids = [r[2] for r in iter_rows(val_files)]
    random.Random(0).shuffle(val_ids)
    val_set = set(val_ids[: args.val_count])

    sources = [("train", sorted(args.raw.glob("train-*.parquet"))), ("validation", val_files)]
    total = sum(pq.ParquetFile(f).metadata.num_rows for _, fs in sources for f in fs)

    def jobs():
        for kind, files in sources:
            for img_b, lbl_b, rid in iter_rows(files):
                split = "train" if kind == "train" else ("val" if rid in val_set else "test")
                yield (img_b, lbl_b, f"{kind}_{rid:05d}", split, args.out, lut, len(names),
                       args.max_side, args.min_area)

    stats = {s: [0] * len(names) for s in ("train", "val", "test")}
    n_img = {s: 0 for s in stats}
    with ProcessPoolExecutor(args.workers) as ex:
        for r in tqdm(ex.map(process, jobs(), chunksize=16), total=total, desc="converting"):
            n_img[r["split"]] += 1
            stats[r["split"]] = [a + b for a, b in zip(stats[r["split"]], r["counts"])]

    data_yaml = {
        "path": str(args.out.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(names)),
    }
    (args.out / "data.yaml").write_text(yaml.safe_dump(data_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (args.out / "stats.json").write_text(json.dumps({"images": n_img, "instances": {
        s: dict(zip(names, c)) for s, c in stats.items()}}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nImages: {n_img}")
    print(f"{'class':<20}{'train':>8}{'val':>8}{'test':>8}")
    for i, n in enumerate(names):
        print(f"{n:<20}{stats['train'][i]:>8}{stats['val'][i]:>8}{stats['test'][i]:>8}")
    print(f"\nDone: {args.out / 'data.yaml'}")


if __name__ == "__main__":
    main()
