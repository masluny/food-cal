"""food-cal tray service: SCAN from the ESP32 display -> photo of the plate -> result back on the screen,
"ADD TODAY" -> food diary (data/diary.csv), Today screen with the date and today's kcal and macros,
EDIT -> list of today's meals with DELETE, CHANGE -> pick the right dish (saved as a training label),
hold the MIC button -> say what you ate -> text (local whisper) -> OpenRouter model -> kcal and macros (src/voice.py).
No Windows notifications — everything shows on the display and in the tray menu.
Every scan is recognized on 4 frames and each region gets the class most frames agree on (src/vote.py).

Runs in the background with an icon in the Windows system tray (the ^ arrow, bottom right corner):
    left click   -> Scan now
    right click  -> menu: status, today's totals, last scan, Scan now, Add last scan to today, Undo last add,
                    Open app, Calibrate scale..., Open diary, Open scans folder, Open log,
                    Start with Windows, Quit
Icon color: green = display connected, orange = waiting for the display, blue = scanning.

    python src/scan_service.py              # run now (log also in the console)
    python src/scan_service.py --install    # start with Windows + start now in the background
    python src/scan_service.py --uninstall  # remove from startup and stop

Log: runs/scan_service.log. Protocol and screens: esp32/food_cal_display/food_cal_display.ino.
- The model runs on the CPU (~0.05 s), so nothing sits on the GPU in the background (games etc.).
- The camera is opened only for a scan; other apps can use it the rest of the time.
- Every scan saves the photo to data/webcam/raw/<time>_scan/ — ready for labeling and fine-tuning.
  RE-SCAN marks the previous photo "rejected" (misrecognized — label it first), ADD marks it "added".
- Only the last 4 days of scans, voice logs, diary rows and log lines are kept (src/retention.py).
"""
import argparse
import json
import logging
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from contextlib import contextmanager
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import cv2
import pystray
import serial
import yaml
from PIL import Image, ImageDraw
from serial.tools import list_ports

import diary
import retention
import voice
from camera import grab_frames, open_camera
from predict import default_weights, estimate_items, load_px_per_cm
from vote import vote

ROOT = Path(__file__).resolve().parents[1]
PYTHONW = ROOT / ".venv/Scripts/pythonw.exe"
LOCK_PORT = 47613                       # port taken = the service is already running
APP_PORT = 7860
USB_IDS = {(0x1A86, 0x7523), (0x1A86, 0x55D4), (0x10C4, 0xEA60), (0x303A, 0x1001)}  # CH340, CH9102, CP210x, ESP32-S3
HEARTBEAT_S = 4
TODAY_PUSH_S = 60                       # resend the Today totals (date rolls over at midnight)
MAX_VOICE_S = float(voice.load_cfg().get("max_seconds", 20))
STARTUP_LNK = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/food-cal-scan.lnk"
NICE = {"cheese_butter": "cheese/butter", "breaded_cutlet": "breaded cutlet", "hot_dog": "hot dog",
        "coffee_tea": "coffee/tea", "milk_drink": "milk drink"}
CLASSES = [c["name"] for c in yaml.safe_load((ROOT / "configs/classes.yaml").read_text(encoding="utf-8"))["classes"]]
# CHANGE alternatives when the model itself has no second guess: similar-looking classes
SIMILAR = {
    "toast": ["bread", "zapiekanka", "pizza"], "bread": ["toast", "zapiekanka", "sweets"],
    "zapiekanka": ["toast", "pizza", "bread"], "pizza": ["zapiekanka", "toast", "bread"],
    "pasta": ["rice", "potatoes", "fries"], "rice": ["pasta", "potatoes", "vegetables"],
    "potatoes": ["fries", "rice", "pasta"], "fries": ["potatoes", "breaded_cutlet", "bread"],
    "meat": ["breaded_cutlet", "chicken", "sausage"], "chicken": ["meat", "breaded_cutlet", "fish"],
    "breaded_cutlet": ["meat", "chicken", "fish"], "sausage": ["meat", "breaded_cutlet", "chicken"],
    "fish": ["chicken", "breaded_cutlet", "meat"], "salad": ["vegetables", "fruit", "pasta"],
    "vegetables": ["salad", "fruit", "potatoes"], "fruit": ["vegetables", "sweets", "salad"],
    "sweets": ["bread", "fruit", "toast"], "sauce": ["soup", "cheese_butter", "vegetables"],
    "burger": ["toast", "hot_dog", "bread"], "hot_dog": ["sausage", "burger", "bread"],
    "burrito": ["toast", "zapiekanka", "burger"], "dumplings": ["pasta", "potatoes", "sweets"],
    "drink": ["coffee_tea", "milk_drink", "soup"], "coffee_tea": ["drink", "milk_drink", "soup"],
    "milk_drink": ["coffee_tea", "drink", "soup"],
}
DEFAULT_ALTS = ["toast", "pizza", "pasta", "zapiekanka", "bread"]
NO_WINDOW = subprocess.CREATE_NO_WINDOW

log = logging.getLogger("food-cal")


def setup_logging():
    (ROOT / "runs").mkdir(exist_ok=True)
    if sys.stdout is None:  # pythonw: no console — keep stray prints/tracebacks in a file instead
        sys.stdout = sys.stderr = open(ROOT / "runs/scan_service.out", "a", encoding="utf-8", buffering=1)
    handlers = [RotatingFileHandler(ROOT / "runs/scan_service.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"),
                logging.StreamHandler(sys.stdout)]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=handlers)


def to_ascii(text: str) -> str:
    """The display's built-in fonts are ASCII only (meal names may contain Polish letters)."""
    return text.translate(str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")).encode("ascii", "replace").decode()


def make_icon(rgb: tuple) -> Image.Image:
    """A plate with food, tinted by state."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=rgb + (255,))
    d.ellipse((12, 12, 52, 52), fill=(255, 255, 255, 255))
    d.ellipse((22, 22, 42, 42), fill=rgb + (255,))
    return img


class State:
    def __init__(self):
        self.display = None          # port name while the display is connected
        self.scanning = False
        self.loading = True
        self.last = "no scans yet"
        self.pending = None          # last scan that can still be added: {"msg", "dir"}
        self.list_keys = []          # (time, name, kcal) of the rows last sent to the EDIT screen
        self.recorder = None         # voice.Recorder while the mic button is held
        self.voice_queued = False
        self.requests = queue.Queue()  # actions for the worker thread: "scan", "rescan", "add", "undo"
        self.stop = threading.Event()
        self.icon = None

    def status_text(self) -> str:
        if self.loading:
            return "loading model..."
        if self.recorder is not None:
            return "listening..."
        if self.scanning:
            return "working..."
        return f"display connected ({self.display})" if self.display else "waiting for the display"

    @staticmethod
    def today_text() -> str:
        t = diary.totals()
        return (f"Today: {t['kcal']:.0f} kcal · P {t['protein']:.0f} g · F {t['fat']:.0f} g · "
                f"C {t['carbs']:.0f} g ({t['meals']} meals)")

    def refresh(self):
        if self.icon is None:
            return
        rgb = (40, 120, 220) if self.scanning or self.recorder else (30, 170, 80) if self.display else (230, 140, 30)
        self.icon.icon = make_icon(rgb)
        self.icon.title = f"food-cal: {self.status_text()}\n{self.today_text().split(' · ')[0]}"[:127]
        self.icon.update_menu()



_write_lock = threading.Lock()  # the worker and the keepalive thread both write to the port


def send(ser: serial.Serial | None, msg: dict):
    if ser is not None:
        with _write_lock:
            ser.write((json.dumps(msg, ensure_ascii=True) + "\n").encode())


@contextmanager
def keepalive(ser):
    """Keeps pinging the display while a slow action (scan, waiting for the voice model) blocks the worker
    loop — without it the display decides after 12 s that the PC is off and goes black."""
    done = threading.Event()

    def run():
        while not done.wait(HEARTBEAT_S):
            try:
                ping(ser)
            except Exception:
                return

    threading.Thread(target=run, daemon=True).start()
    try:
        yield
    finally:
        done.set()


def ping(ser):
    """Heartbeat; carries the PC's local time (seconds since 1970, local) — the display keeps counting it alone."""
    send(ser, {"t": "ping", "clock": round((datetime.now() - datetime(1970, 1, 1)).total_seconds())})


def send_today(ser):
    t = diary.totals()
    send(ser, {"t": "today", "date": datetime.now().strftime("%a %d %b %Y"), "kcal": t["kcal"],
               "protein": t["protein"], "fat": t["fat"], "carbs": t["carbs"], "meals": t["meals"],
               "last": to_ascii(t["last"])})


def connect(port_arg: str | None) -> serial.Serial | None:
    """Opens a port and waits for HELLO from our firmware (other CH340 devices are skipped)."""
    ports = [port_arg] if port_arg else [p.device for p in list_ports.comports() if (p.vid, p.pid) in USB_IDS]
    for dev in ports:
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = dev, 115200, 0.5
            ser.dtr = ser.rts = False  # otherwise opening the port resets the ESP32 / leaves it in the bootloader
            ser.open()
        except serial.SerialException as e:
            log.info(f"{dev}: cannot open ({e})")
            continue
        deadline = time.time() + 7
        while time.time() < deadline:
            line = ser.readline().decode(errors="replace").strip()
            if line.startswith("HELLO food-cal") or line in ("SCAN", "RESCAN", "ADD"):
                ping(ser)
                send_today(ser)
                log.info(f"Display connected on {dev} ({line})")  # HELLO has uptime + reset reason
                return ser
        ser.close()
    return None


def describe(est: dict, calibrated: bool) -> dict:
    """`estimate` result -> display message (dish name, total kcal and macros, up to 2 detail lines)."""
    key = (lambda kv: -kv[1]["kcal"]) if calibrated else (lambda kv: -kv[1]["confidence"])
    items = sorted(est.items(), key=key)
    label = lambda n, r: NICE.get(n, n.replace("_", " ")) + (f" x{r['count']}" if r["count"] > 1 else "")

    main = [items[0]]
    if calibrated:
        total = sum(r["kcal"] for _, r in items) or 1
        main += [kv for kv in items[1:] if kv[1]["kcal"] >= 0.15 * total][:1]
    elif len(items) > 1:
        main.append(items[1])
    name = " + ".join(label(n, r) for n, r in main)

    if not calibrated:
        lines = [", ".join(f"{label(n, r)} {r['confidence']:.0%}" for n, r in items[:4])]
        return {"t": "result", "name": to_ascii(name), "kcal": None, "lines": [to_ascii(l) for l in lines]}

    lines = [f"{label(n, r)}: {r['kcal']:.0f} kcal ({r['g']:.0f} g)" for n, r in items[:2]]
    if len(items) > 2:
        lines[-1] += f"  +{len(items) - 2} more"
    tot = {k: sum(r[k] for _, r in items) for k in ("kcal", "protein", "fat", "carbs", "g")}
    return {"t": "result", "name": to_ascii(name), "kcal": round(tot["kcal"]),
            "lo": round(sum(r["kcal"] * (1 - r["uncertainty"]) for _, r in items)),
            "hi": round(sum(r["kcal"] * (1 + r["uncertainty"]) for _, r in items)),
            "protein": round(tot["protein"], 1), "fat": round(tot["fat"], 1), "carbs": round(tot["carbs"], 1),
            "g": round(tot["g"]), "lines": [to_ascii(l) for l in lines]}


def save_scan(img, est: dict, name: str | None) -> Path:
    d = ROOT / "data/webcam/raw" / f"{datetime.now():%Y%m%d_%H%M%S}_scan"
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "01.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    (d / "meta.json").write_text(json.dumps({"name": name, "time": datetime.now().isoformat(timespec="seconds"),
                                             "source": "esp32", "prediction": est}, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    return d


def mark_scan(scan_dir: Path | None, **fields):
    """Adds flags to a saved scan's meta.json (rejected = misrecognized, added = went to the diary)."""
    if scan_dir is None or not (scan_dir / "meta.json").exists():
        return
    meta = json.loads((scan_dir / "meta.json").read_text(encoding="utf-8"))
    meta.update(fields)
    (scan_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def favorite_classes() -> list[str]:
    """Classes you eat most often, from the diary (the first item of each saved dish name)."""
    back = {NICE.get(c, c.replace("_", " ")): c for c in CLASSES}
    counts = {}
    for r in diary._rows():
        first = r["name"].split(" + ")[0].rsplit(" x", 1)[0]
        if first in back:
            counts[back[first]] = counts.get(back[first], 0) + 1
    return sorted(counts, key=lambda c: -counts[c])


def plate_message(p: dict) -> dict:
    """Display message for the pending scan: result + up to 3 alternatives for the main region (CHANGE)."""
    regions, main = p["regions"], p["regions"][p["main"]]
    items = lambda: [(r.name, r.conf, r.area) for r in regions]
    msg = describe(estimate_items(items(), p["nutrition"], p["px"]), p["px"] is not None)

    cands = [n for n, s in main.scores.items() if s >= 0.02] + favorite_classes() + \
        SIMILAR.get(main.name, []) + DEFAULT_ALTS
    alts, current = [], main.name
    for n in cands:
        if n == current or n in alts or n not in p["nutrition"]:
            continue
        alts.append(n)
        if len(alts) == 3:
            break
    out = []
    for n in alts:  # total plate kcal if the main region were this class
        main.name = n
        e = estimate_items(items(), p["nutrition"], p["px"])
        out.append({"name": to_ascii(NICE.get(n, n.replace("_", " "))),
                    "kcal": round(sum(r["kcal"] for r in e.values())) if p["px"] else None,
                    "conf": round(main.scores.get(n, 0.0), 2)})
    main.name = current
    p["alts"] = alts
    msg["alts"] = out
    return msg


def write_labels(scan_dir: Path | None, p: dict):
    """LabelMe .json next to the scan photo (opens in X-AnyLabeling; prepare_webcam.py uses it for training)."""
    if scan_dir is None:
        return
    h, w = p["shape"]
    shapes = [{"label": r.name, "points": poly.round(1).tolist(), "shape_type": "polygon", "flags": {},
               "description": "corrected by user" if i == p["main"] else f"auto {r.conf:.2f}"}
              for i, r in enumerate(p["regions"]) for poly in r.polys]
    (scan_dir / "01.json").write_text(json.dumps({"version": "2.4.0", "flags": {}, "shapes": shapes,
                                                  "imagePath": "01.jpg", "imageData": None, "imageHeight": h,
                                                  "imageWidth": w}, indent=1), encoding="utf-8")


def scan(ser, model, args, state: State):
    t0 = time.time()
    state.pending = None
    send(ser, {"t": "status", "msg": "Taking photo..."})
    cam_cfg = ROOT / "configs/camera.yaml"
    cam_idx = yaml.safe_load(cam_cfg.read_text())["camera"] if cam_cfg.exists() else 0
    try:
        cap = open_camera(cam_idx)
        try:
            frames = grab_frames(cap)[:args.frames]
        finally:
            cap.release()
    except Exception as e:
        log.info(f"Camera: {e}")
        send(ser, {"t": "error", "msg": "Camera busy or unplugged"})
        return

    send(ser, {"t": "status", "msg": "Recognizing..."})
    img = frames[0]
    nutrition = yaml.safe_load((ROOT / "configs/nutrition.yaml").read_text(encoding="utf-8"))
    results = [model(f, conf=0.05, imgsz=640, device=args.device, verbose=False)[0] for f in frames]
    regions = vote(results, conf_thr=args.conf)
    px_per_cm = load_px_per_cm(None, img.shape[1])  # read on every scan: a new calibration works immediately
    stamp = datetime.now().strftime("%H:%M")
    if not regions:
        send(ser, {"t": "error", "msg": "Nothing recognized"})
        state.last = f"{stamp} nothing recognized"
        if args.save:
            save_scan(img, {}, None)
        log.info(f"Scan: nothing recognized ({time.time() - t0:.1f} s)")
        return

    est = estimate_items([(r.name, r.conf, r.area) for r in regions], nutrition, px_per_cm)
    kcal_of = lambda r: est[r.name].get("kcal", 0) * r.area / max(sum(x.area for x in regions if x.name == r.name), 1)
    main = max(range(len(regions)), key=lambda i: kcal_of(regions[i]) if px_per_cm else regions[i].conf)
    p = {"regions": regions, "main": main, "nutrition": nutrition, "px": px_per_cm, "shape": img.shape[:2]}
    msg = plate_message(p)
    send(ser, msg)
    if msg["kcal"] is None:
        summary = f"{msg['name']} (no scale calibration)"
    else:
        summary = (f"{msg['name']}: {msg['kcal']} kcal ({msg['lo']}-{msg['hi']})\n"
                   f"Protein {msg['protein']:.0f} g · Fat {msg['fat']:.0f} g · Carbs {msg['carbs']:.0f} g")
    state.last = f"{stamp} " + summary.split("\n")[0]
    p["dir"] = save_scan(img, est, msg["name"]) if args.save else None
    p["msg"] = msg
    state.pending = p
    log.info(f"Scan: {msg['name']} {msg['kcal']} kcal, {len(frames)} frames, alternatives "
             f"{p['alts']} ({time.time() - t0:.1f} s) -> {p['dir'] or '-'}")


def pick(ser, state: State, index: int):
    """CHANGE on the display: the main region becomes alternative `index`; saved as a label for training."""
    p = state.pending
    if p is None or not 0 <= index < len(p.get("alts", [])):
        send(ser, {"t": "error", "msg": "Nothing to change - scan again"})
        return
    main = p["regions"][p["main"]]
    old, main.name = main.name, p["alts"][index]
    msg = plate_message(p)
    p["msg"] = msg
    send(ser, msg)
    mark_scan(p["dir"], name=msg["name"], correction={"from": old, "to": main.name})
    write_labels(p["dir"], p)
    state.last = f"{datetime.now():%H:%M} {msg['name']}: {msg['kcal']} kcal (corrected)"
    log.info(f"Corrected: {old} -> {main.name} ({msg['kcal']} kcal), label saved to {p['dir'] or '-'}")


def add_pending(ser, state: State):
    p = state.pending
    if p is None:
        send(ser, {"t": "error", "msg": "Nothing to add - scan first"})
        return
    m = p["msg"]
    if m["kcal"] is None:
        send(ser, {"t": "error", "msg": "Calibrate the scale first"})
        return
    try:
        source = (f"voice: {p['voice']}" if p.get("voice") else
                  str(p["dir"].relative_to(ROOT) if p["dir"] and p["dir"].is_relative_to(ROOT) else p["dir"] or ""))
        diary.add(m["name"], m["kcal"], m["protein"], m["fat"], m["carbs"], m.get("g", 0), source)
    except PermissionError:  # diary.csv open in Excel
        send(ser, {"t": "error", "msg": "Close diary.csv in Excel first"})
        return
    mark_scan(p["dir"], added=True)
    state.pending = None
    send_today(ser)
    t = diary.totals()
    log.info(f"Added to diary: {m['name']} {m['kcal']} kcal (today {t['kcal']:.0f} kcal)")


def undo_last(ser, state: State):
    try:
        row = diary.undo_last_today()
    except PermissionError:
        return
    if row:
        send_today(ser)
        log.info(f"Removed from diary: {row['name']} {row['kcal']} kcal")


def start_listening(ser, state: State):
    cfg = voice.load_cfg()
    try:
        state.recorder = voice.Recorder(cfg.get("mic_device"))
        state.recorder.start()
    except Exception as e:
        state.recorder = None
        log.info(f"Microphone: {e}")
        send(ser, {"t": "error", "msg": "No microphone"})
        return
    state.voice_queued = False
    state.refresh()
    threading.Thread(target=voice.preload, args=(cfg["whisper_model"],), daemon=True).start()
    log.info("Listening...")


def voice_meal(ser, state: State):
    """Mic button released: audio -> text (whisper on the CPU) -> OpenRouter -> result on the display."""
    rec, state.recorder = state.recorder, None
    state.voice_queued = False
    if rec is None or not rec.active:
        send(ser, {"t": "error", "msg": "Hold the mic button while speaking"})
        return
    audio = rec.stop()
    if len(audio) < 0.5 * 16000:
        send(ser, {"t": "error", "msg": "Too short - hold the button and speak"})
        return
    t0, cfg = time.time(), voice.load_cfg()
    send(ser, {"t": "status", "msg": "Transcribing..."})
    text, lang = voice.transcribe(audio, cfg["whisper_model"], cfg.get("language"))
    log.info(f"Voice ({lang}, {len(audio) / 16000:.1f} s audio, {time.time() - t0:.1f} s): {text!r}")
    if not text:
        send(ser, {"t": "error", "msg": "Didn't catch that - try again"})
        return
    send(ser, {"t": "status", "msg": "Asking the model..."})
    try:
        ans = voice.ask_llm(text, cfg, on_status=lambda m: send(ser, {"t": "status", "msg": m}))
    except Exception as e:
        log.info(f"Language model: {e}")
        send(ser, {"t": "error", "msg": "API key missing - see secrets.yaml" if "is empty" in str(e)
                   else "Key spending limit reached - see OpenRouter" if "limit" in str(e).lower() or " 402:" in str(e)
                   else "Model unavailable - see log"})
        return
    if ans.get("error") or not ans.get("items") or not ans.get("kcal"):
        send(ser, {"t": "error", "msg": "Not food? Try again"})
        return
    u = min(max(float(ans.get("uncertainty") or 0.3), 0.1), 0.6)
    kcal = float(ans["kcal"])
    items = ", ".join(f"{i.get('name', '?')} {round(float(i.get('kcal') or 0))}" for i in ans["items"])
    name = to_ascii(ans.get("name") or "meal")
    if len(name) > 22:  # cut at a word boundary
        name = name[:23].rsplit(" ", 1)[0].rstrip(" ,&-")
    msg = {"t": "result", "name": name, "kcal": round(kcal),
           "lo": round(kcal * (1 - u)), "hi": round(kcal * (1 + u)), "protein": ans["protein"], "fat": ans["fat"],
           "carbs": ans["carbs"], "g": round(ans["grams"]), "lines": [to_ascii(f'"{text}"'), to_ascii(items)],
           "alts": []}
    send(ser, msg)
    state.pending = {"msg": msg, "dir": None, "voice": text}
    state.last = f"{datetime.now():%H:%M} {msg['name']}: {msg['kcal']} kcal (voice)"
    vdir = ROOT / "data/voice"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{datetime.now():%Y%m%d_%H%M%S}.json").write_text(json.dumps(
        {"time": datetime.now().isoformat(timespec="seconds"), "text": text, "language": lang, "answer": ans},
        indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Voice result: {msg['name']} {msg['kcal']} kcal via {ans.get('model')} ({time.time() - t0:.1f} s total)")


def send_list(ser, state: State):
    """Today's meals for the EDIT screen, newest first (max 40). Remembers which row each index means."""
    rows = list(reversed(diary.today_rows()))[:40]
    state.list_keys = [(r["time"], r["name"], r["kcal"]) for r in rows]
    send(ser, {"t": "list", "items": [{"time": r["time"], "name": to_ascii(r["name"]), "kcal": round(float(r["kcal"]))}
                                      for r in rows]})


def delete_item(ser, state: State, index: int):
    if not 0 <= index < len(state.list_keys):
        send_list(ser, state)
        return
    try:
        row = diary.delete(*state.list_keys[index])
    except PermissionError:
        send(ser, {"t": "error", "msg": "Close diary.csv in Excel first"})
        return
    if row:
        log.info(f"Removed from diary (display): {row['name']} {row['kcal']} kcal")
    send_today(ser)
    send_list(ser, state)


def worker(state: State, args):
    from ultralytics import YOLO
    weights = args.weights or default_weights()
    model = YOLO(weights)
    state.loading = False
    state.refresh()
    log.info(f"Model: {weights} ({args.device}). Waiting for the display...")

    ser, last_ping, last_today, day, pruned = None, 0.0, time.time(), date.today(), None
    while not state.stop.is_set():
        try:
            if pruned != date.today():  # at start and after every midnight: keep only the last few days
                pruned = date.today()
                retention.prune()
            if ser is None:
                ser = connect(args.port)
                state.display = ser.port if ser else None
                state.refresh()
            if ser is not None:
                now = time.time()
                if now - last_ping > HEARTBEAT_S:
                    ping(ser)
                    last_ping = now
                if now - last_today > TODAY_PUSH_S or date.today() != day:
                    send_today(ser)
                    last_today, day = now, date.today()
                    state.refresh()
                line = ser.readline().decode(errors="replace").strip()
                if line in ("SCAN", "RESCAN", "ADD", "LIST"):
                    state.requests.put(line.lower())
                elif line.startswith("DEL ") and line[4:].isdigit():
                    state.requests.put(("del", int(line[4:])))
                elif line.startswith("PICK ") and line[5:].isdigit():
                    state.requests.put(("pick", int(line[5:])))
                elif line == "MIC_START":
                    start_listening(ser, state)  # right away, not via the queue: recording must not lag
                elif line == "MIC_STOP" and not state.voice_queued:
                    state.voice_queued = True
                    state.requests.put("voice")
                elif line == "CANCEL":
                    state.requests.put("cancel")  # X while waiting: queued, so it runs after the cancelled action
                elif line.startswith("TOUCH"):
                    log.info(f"Display {line}")  # touch coordinates — for checking the touch calibration
                rec = state.recorder
                if rec is not None and rec.seconds > MAX_VOICE_S and not state.voice_queued:
                    state.voice_queued = True    # the button was held too long: stop and process anyway
                    state.requests.put("voice")
            try:
                action = state.requests.get(timeout=0.05 if ser else 3)
            except queue.Empty:
                continue
            log.info(f"Action: {action}")
            if action == "cancel":
                state.pending = None   # the display dropped the answer — "Add last scan" must not add it either
            elif action == "add":
                add_pending(ser, state)
            elif action == "undo":
                undo_last(ser, state)
            elif action == "list":
                send_list(ser, state)
            elif isinstance(action, tuple) and action[0] == "del":
                delete_item(ser, state, action[1])
            elif isinstance(action, tuple) and action[0] == "pick":
                pick(ser, state, action[1])
            elif action == "voice":
                state.scanning = True
                state.refresh()
                try:
                    with keepalive(ser):
                        voice_meal(ser, state)
                finally:
                    state.scanning = False
                    last_ping = time.time()
            else:
                if action == "rescan" and state.pending:
                    mark_scan(state.pending["dir"], rejected=True)
                state.scanning = True
                state.refresh()
                try:
                    with keepalive(ser):
                        scan(ser, model, args, state)
                finally:
                    state.scanning = False
                    last_ping = time.time()
            state.refresh()
        except serial.SerialException as e:
            log.info(f"Display disconnected ({e}) — searching again")
            ser.close()
            ser = state.display = None
            state.refresh()
        except Exception:
            log.exception("Error")
            try:
                send(ser, {"t": "error", "msg": "Error on PC - see log"})
            except Exception:
                ser = state.display = None
    if ser is not None:
        ser.close()


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def set_autostart(enabled: bool):
    if not enabled:
        STARTUP_LNK.unlink(missing_ok=True)
        return
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{STARTUP_LNK}'); "
          f"$s.TargetPath = '{PYTHONW}'; $s.Arguments = '\"{ROOT / 'src/scan_service.py'}\"'; "
          f"$s.WorkingDirectory = '{ROOT}'; $s.Description = 'food-cal tray service'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=NO_WINDOW)


def build_tray(state: State) -> pystray.Icon:
    def spawn(script: str, *extra):
        subprocess.Popen([str(PYTHONW), str(ROOT / "src" / script), *extra], cwd=ROOT, creationflags=NO_WINDOW)

    def open_app(icon, item):
        if port_open(APP_PORT):
            webbrowser.open(f"http://127.0.0.1:{APP_PORT}")
        else:
            spawn("app.py", "--open-browser")

    def open_diary(icon, item):
        if not diary.PATH.exists():
            return
        os.startfile(diary.PATH)

    def quit_app(icon, item):
        state.stop.set()
        icon.stop()

    def toggle_autostart(icon, item):
        set_autostart(not STARTUP_LNK.exists())
        icon.update_menu()

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: f"Status: {state.status_text()}", None, enabled=False),
        pystray.MenuItem(lambda item: state.today_text(), None, enabled=False),
        pystray.MenuItem(lambda item: f"Last scan: {state.last}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Scan now", lambda icon, item: state.requests.put("scan"), default=True),
        pystray.MenuItem("Add last scan to today", lambda icon, item: state.requests.put("add"),
                         enabled=lambda item: state.pending is not None),
        pystray.MenuItem("Undo last add", lambda icon, item: state.requests.put("undo"),
                         enabled=lambda item: diary.totals()["meals"] > 0),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open app", open_app),
        pystray.MenuItem("Calibrate scale...", lambda icon, item: spawn("calibrate.py")),
        pystray.MenuItem("Open diary", open_diary),
        pystray.MenuItem("Open scans folder", lambda icon, item: os.startfile(ROOT / "data/webcam/raw")),
        pystray.MenuItem("Open log", lambda icon, item: os.startfile(ROOT / "runs/scan_service.log")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", toggle_autostart, checked=lambda item: STARTUP_LNK.exists()),
        pystray.MenuItem("Quit", quit_app),
    )
    return pystray.Icon("food-cal", make_icon((150, 150, 150)), "food-cal: loading model...", menu)


def run(args):
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        log.info("The service is already running — exiting.")
        return
    state = State()
    state.icon = build_tray(state)
    threading.Thread(target=worker, args=(state, args), daemon=True).start()
    state.icon.run()  # tray loop in the main thread; returns after Quit
    state.stop.set()
    log.info("Stopped.")


def install():
    set_autostart(True)
    # start through Explorer, so the service doesn't belong to (and die with) the terminal that ran --install
    subprocess.run(["explorer.exe", str(STARTUP_LNK)])
    print(f"Startup shortcut: {STARTUP_LNK}\nThe service is starting — look for the icon under the ^ arrow in the taskbar.\n"
          f"Log: {ROOT / 'runs/scan_service.log'}")


def uninstall():
    set_autostart(False)
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*scan_service.py*' -and "
          f"$_.ProcessId -ne {os.getpid()} }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=NO_WINDOW)
    print("Removed from startup and stopped the service.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="e.g. COM3; found automatically by default")
    ap.add_argument("--weights", type=Path)
    ap.add_argument("--device", default="cpu", help="cpu or 0 (GPU)")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--frames", type=int, default=4, help="frames per scan for majority voting")
    ap.add_argument("--no-save", dest="save", action="store_false", help="don't save scan photos")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()
    if args.install:
        return install()
    if args.uninstall:
        return uninstall()
    setup_logging()
    run(args)


if __name__ == "__main__":
    main()
