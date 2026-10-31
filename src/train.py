"""Train YOLO-seg on food components.

Stage 1 (done):  python src/train.py --name foodseg_s
Stage 2 (done):  python src/train.py --data data/processed/combined.yaml \
                     --model runs/foodseg_s/weights/best.pt --epochs 30 --name combined_s
Stage 3 (+ burger, hot_dog, burrito, dumplings, coffee_tea, milk_drink):
                 python src/train.py --data data/processed/combined_v2.yaml \
                     --model runs/combined_s/weights/best.pt --epochs 40 --name combined_v2
Your photos:     python src/train.py --data data/processed/webcam_yolo/data.yaml \
                     --model runs/combined_s/weights/best.pt --epochs 60 --flipud 0.5 --name webcam_s

Resume an interrupted run:  python src/train.py --resume --name foodseg_s
"""
import argparse
import sys
from pathlib import Path

from ultralytics import YOLO

from webcam_aug import webcam_augmentations

ROOT = Path(__file__).resolve().parents[1]


def batch_arg(v: str):
    f = float(v)
    return int(f) if f.is_integer() else f  # -1 = auto (60% VRAM), 16 = fixed, 0.7 = 70% VRAM


def keep_awake():
    """Windows: no sleep in the middle of a training run (the screen can still turn off). Lasts while we run."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


def main():
    keep_awake()
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data/processed/foodseg_yolo/data.yaml")
    ap.add_argument("--model", default="yolo26s-seg.pt",
                    help="weights name (downloaded to models/) or path to a .pt")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=batch_arg, default=-1)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--patience", type=int, default=20, help="stop if no improvement for N epochs")
    ap.add_argument("--fraction", type=float, default=1.0, help="fraction of the training set")
    ap.add_argument("--flipud", type=float, default=0.0, help="0.5 for top-down photos")
    ap.add_argument("--no-webcam-aug", action="store_true")
    ap.add_argument("--name", default="foodseg_s")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    if args.resume:
        YOLO(ROOT / "runs" / args.name / "weights/last.pt").train(resume=True)
        return

    model_path = Path(args.model)
    if not model_path.exists():
        model_path = ROOT / "models" / args.model

    model = YOLO(model_path)
    model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        patience=args.patience,
        fraction=args.fraction,
        flipud=args.flipud,
        augmentations=None if args.no_webcam_aug else webcam_augmentations(),
        project=str(ROOT / "runs"),
        name=args.name,
        seed=0,
    )

    best = Path(model.trainer.save_dir) / "weights/best.pt"
    print(f"\nFinal evaluation on the test split ({best}):")
    YOLO(best).val(data=str(args.data), split="test", imgsz=args.imgsz, project=str(ROOT / "runs"),
                   name=f"{args.name}_test")


if __name__ == "__main__":
    main()
