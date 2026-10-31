"""Shared webcam helpers: open with settings and pick the sharpest frame."""
import time

import cv2
import numpy as np


def open_camera(index: int = 0, width: int = 1920, height: int = 1080) -> cv2.VideoCapture:
    # DirectShow on Windows: opens faster and allows opening the driver's settings dialog
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {index}. Check: python src/capture.py --list")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # higher resolution over USB 2.0
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    for _ in range(10):  # the first frames are often dark until auto-exposure settles
        cap.read()
    return cap


def list_cameras(max_index: int = 6) -> list[tuple[int, int, int]]:
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                found.append((i, frame.shape[1], frame.shape[0]))
        cap.release()
    return found


def sharpness(frame: np.ndarray) -> float:
    """Variance of the Laplacian — higher means sharper."""
    return float(cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def grab_frames(cap: cv2.VideoCapture, n: int = 8, delay: float = 0.05) -> list[np.ndarray]:
    """n frames, sharpest first."""
    frames = []
    for _ in range(n):
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
        time.sleep(delay)
    if not frames:
        raise RuntimeError("The camera returned no frames — is another app using it (Camera, Teams, Discord)? "
                           "Close it and try again.")
    return sorted(frames, key=sharpness, reverse=True)


def grab_sharpest(cap: cv2.VideoCapture, n: int = 8, delay: float = 0.05) -> np.ndarray:
    return grab_frames(cap, n, delay)[0]
