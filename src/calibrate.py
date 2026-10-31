"""Scale calibration: how many pixels make 1 cm at plate height. Do it once after mounting the camera.

    python src/calibrate.py        (or: tray icon -> "Calibrate scale...")

Put a plate (or an A4 sheet — 29.7 x 21 cm) where you eat. Click two points on opposite edges,
press any key, then type the real distance in cm in the dialog. No terminal needed.
The result goes to configs/camera.yaml. Recalibrate whenever the camera moves.
With an angled camera the scale is only correct where the sheet was lying.
"""
import argparse
import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

import cv2
import yaml

from camera import grab_sharpest, open_camera

ROOT = Path(__file__).resolve().parents[1]
WIN = "Calibration: click 2 points, then press any key (Esc = cancel)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        cap = open_camera(args.camera, args.width, args.height)
        frame = grab_sharpest(cap)
        cap.release()
    except RuntimeError as e:
        messagebox.showerror("food-cal calibration", str(e), parent=root)
        return

    scale = 1280 / frame.shape[1]
    view = cv2.resize(frame, None, fx=scale, fy=scale)
    points = []

    def on_click(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
            points.append((x / scale, y / scale))
            cv2.circle(view, (x, y), 6, (0, 0, 255), -1)
            if len(points) == 2:
                p1, p2 = [(int(px * scale), int(py * scale)) for px, py in points]
                cv2.line(view, p1, p2, (0, 0, 255), 2)

    cv2.namedWindow(WIN)
    cv2.setWindowProperty(WIN, cv2.WND_PROP_TOPMOST, 1)
    cv2.setMouseCallback(WIN, on_click)
    while True:
        cv2.imshow(WIN, view)
        key = cv2.waitKey(20)
        if key == 27 or cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            cv2.destroyAllWindows()
            return
        if key != -1 and len(points) == 2:
            break
    cv2.destroyAllWindows()

    dist_px = math.dist(*points)
    dist_cm = simpledialog.askfloat("food-cal calibration",
                                    f"Distance in the photo: {dist_px:.0f} px.\nWhat is the real distance in cm?",
                                    parent=root, minvalue=0.5, maxvalue=500)
    if not dist_cm:
        return
    cfg = {"camera": args.camera, "width": frame.shape[1], "height": frame.shape[0],
           "px_per_cm": round(dist_px / dist_cm, 3)}
    out = ROOT / "configs/camera.yaml"
    out.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    msg = f"Saved: {cfg['px_per_cm']} px/cm at {cfg['width']}x{cfg['height']}.\nThe field of view is about " \
          f"{cfg['width'] / cfg['px_per_cm']:.0f} x {cfg['height'] / cfg['px_per_cm']:.0f} cm."
    print(msg)
    messagebox.showinfo("food-cal calibration", msg, parent=root)


if __name__ == "__main__":
    main()
