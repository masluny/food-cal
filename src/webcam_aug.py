"""Augmentations that mimic a cheap webcam: blur, low resolution, noise, white balance,
dim light, JPEG compression. Pixel-level only — masks are untouched.

Preview:  python src/webcam_aug.py  ->  runs/aug_preview.jpg
"""
import albumentations as A


def webcam_augmentations() -> list:
    return [
        A.OneOf([
            A.GaussianBlur(blur_limit=(3, 7)),
            A.MotionBlur(blur_limit=(3, 9)),
            A.Defocus(radius=(1, 3)),
        ], p=0.35),
        A.Downscale(scale_range=(0.35, 0.75), p=0.3),
        A.OneOf([
            A.GaussNoise(std_range=(0.02, 0.08)),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5)),
        ], p=0.4),
        A.PlanckianJitter(mode="blackbody", p=0.3),
        A.RandomBrightnessContrast(brightness_limit=(-0.3, 0.15), contrast_limit=(-0.25, 0.1), p=0.4),
        A.RandomGamma(gamma_limit=(80, 140), p=0.2),
        A.ImageCompression(quality_range=(30, 85), p=0.5),
    ]


if __name__ == "__main__":
    import random
    from pathlib import Path

    import cv2
    import numpy as np

    root = Path(__file__).resolve().parents[1]
    imgs = sorted((root / "data/processed/foodseg_yolo/images/val").glob("*.jpg"))
    aug = A.Compose(webcam_augmentations())
    random.seed(0)
    rows = []
    for p in random.sample(imgs, 3):
        img = cv2.resize(cv2.imread(str(p)), (320, 240))
        rows.append(np.hstack([img] + [aug(image=img)["image"] for _ in range(3)]))
    out = root / "runs/aug_preview.jpg"
    out.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(out), np.vstack(rows))
    print(f"Original in the left column, 3 random versions next to it -> {out}")
