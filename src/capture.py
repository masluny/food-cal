"""Collect meal photos from the webcam (training data).

    python src/capture.py            # camera 0
    python src/capture.py --list     # list available cameras

Keys in the preview window:
    N      new meal (type the name and an optional description in the terminal)
    SPACE  take a photo (sharpest of several frames) — take 3-5 per meal, moving the plate a little
    S      camera settings dialog (turn off auto exposure/white balance/focus once the image looks good)
    Q      quit

Each meal goes to its own folder data/webcam/raw/<date>_<name>/ — the train/test split is done
by meal later, not by photo. (The "Save to training data" button in the app does the same.)
"""
import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import cv2

from camera import grab_sharpest, list_cameras, open_camera, sharpness

ROOT = Path(__file__).resolve().parents[1]


def slug(text: str) -> str:
    text = text.lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))  # Polish letters -> ASCII
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "meal"


def new_meal(out_root: Path) -> Path:
    name = input("\nMeal name (e.g. cheese toasts): ").strip()
    desc = input("Ingredients / amounts, if known (e.g. 2 slices of toast bread, 2 slices of cheese): ").strip()
    meal_dir = out_root / f"{datetime.now():%Y%m%d_%H%M%S}_{slug(name)}"
    meal_dir.mkdir(parents=True)
    (meal_dir / "meta.json").write_text(json.dumps(
        {"name": name, "description": desc, "time": datetime.now().isoformat(timespec="seconds"), "source": "capture"},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Meal: {meal_dir.name} — go back to the preview window and press SPACE to take photos")
    return meal_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--out", type=Path, default=ROOT / "data/webcam/raw")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        cams = list_cameras()
        print("\n".join(f"camera {i}: {w}x{h}" for i, w, h in cams) or "No camera found")
        return

    cap = open_camera(args.camera, args.width, args.height)
    meal_dir, shots = None, 0
    print(__doc__)
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No image from the camera")
            break
        view = frame.copy()
        status = f"{meal_dir.name if meal_dir else 'N = new meal'} | photos: {shots} | sharpness: {sharpness(frame):.0f}"
        cv2.putText(view, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(view, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        scale = 960 / view.shape[1]
        cv2.imshow("food-cal capture", cv2.resize(view, None, fx=scale, fy=scale))

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s"):
            cap.set(cv2.CAP_PROP_SETTINGS, 1)
        if key == ord("n"):
            meal_dir, shots = new_meal(args.out), 0
        if key == ord(" "):
            if meal_dir is None:
                print("Press N first — new meal")
                continue
            img = grab_sharpest(cap)
            shots += 1
            path = meal_dir / f"{shots:02d}_{int(time.time())}.jpg"
            cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"  saved {path.name} ({img.shape[1]}x{img.shape[0]}, sharpness {sharpness(img):.0f})")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
