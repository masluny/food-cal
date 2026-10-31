"""Web app: plate photo -> components, grams, kcal and macros.

    python src/app.py                  # then open http://127.0.0.1:7860
    python src/app.py --open-browser   # opens the browser itself (used by the tray icon)

Photo: the "Webcam" button (OpenCV, sharpest of several frames), upload, or the browser camera.
"Save to training data" stores the photo in data/webcam/raw/ for later fine-tuning.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import gradio as gr
import pandas as pd
import yaml
from ultralytics import YOLO

from camera import grab_sharpest, open_camera
from capture import slug
from predict import default_weights, estimate, load_px_per_cm

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["item", "count", "cm²", "g", "kcal", "kcal min", "kcal max", "protein", "fat", "carbs", "confidence"]


def build(weights: Path, camera_index: int) -> gr.Blocks:
    model = YOLO(weights)
    nutrition = yaml.safe_load((ROOT / "configs/nutrition.yaml").read_text(encoding="utf-8"))
    enhancer = {}

    def analyze(img_rgb, conf, portion, denoise=False):
        if img_rgb is None:
            return None, pd.DataFrame(columns=COLUMNS), "No photo."
        bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        if denoise:
            if "scunet" not in enhancer:
                from enhance import ENHANCERS, Enhancer
                enhancer["scunet"] = Enhancer(ENHANCERS["scunet"])
            bgr = enhancer["scunet"](bgr)
        result = model(bgr, conf=conf, imgsz=640, retina_masks=True, verbose=False)[0]
        px_per_cm = load_px_per_cm(None, bgr.shape[1])
        est = estimate(result, nutrition, px_per_cm)
        plot = cv2.cvtColor(result.plot(), cv2.COLOR_BGR2RGB)
        if not est:
            return plot, pd.DataFrame(columns=COLUMNS), "Nothing recognized."
        if not px_per_cm:
            rows = [[n, r["count"]] + [None] * 8 + [round(r["confidence"], 2)] for n, r in est.items()]
            return plot, pd.DataFrame(rows, columns=COLUMNS), "No scale calibration — run `python src/calibrate.py`."
        rows = []
        for n, r in sorted(est.items(), key=lambda kv: -kv[1]["kcal"]):
            k, u = r["kcal"] * portion, r["uncertainty"]
            rows.append([n, r["count"], round(r["cm2"]), round(r["g"] * portion), round(k), round(k * (1 - u)),
                         round(k * (1 + u)), round(r["protein"] * portion, 1), round(r["fat"] * portion, 1),
                         round(r["carbs"] * portion, 1), round(r["confidence"], 2)])
        df = pd.DataFrame(rows, columns=COLUMNS)
        total = (f"### Total: **{df['kcal'].sum():.0f} kcal** ({df['kcal min'].sum():.0f}–{df['kcal max'].sum():.0f})\n"
                 f"Protein {df['protein'].sum():.1f} g · Fat {df['fat'].sum():.1f} g · Carbs {df['carbs'].sum():.1f} g · "
                 f"{df['g'].sum():.0f} g of food")
        return plot, df, total

    def from_camera():
        cap = open_camera(camera_index)
        try:
            return cv2.cvtColor(grab_sharpest(cap), cv2.COLOR_BGR2RGB)
        finally:
            cap.release()

    def save(img_rgb, meal_name, table):
        if img_rgb is None:
            return "No photo to save."
        meal_dir = ROOT / "data/webcam/raw" / f"{datetime.now():%Y%m%d_%H%M%S}_{slug(meal_name or 'meal')}"
        meal_dir.mkdir(parents=True)
        cv2.imwrite(str(meal_dir / "01.jpg"), cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
        meta = {"name": meal_name, "time": datetime.now().isoformat(timespec="seconds"), "source": "app",
                "prediction": table.to_dict(orient="records") if table is not None else []}
        (meal_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return f"Saved: {meal_dir.relative_to(ROOT)}"

    with gr.Blocks(title="food-cal") as demo:
        gr.Markdown(f"## food-cal — what's on the plate?\nModel: `{weights.relative_to(ROOT)}`")
        with gr.Row():
            with gr.Column():
                img = gr.Image(sources=["upload", "webcam"], type="numpy", label="Plate photo")
                cam_btn = gr.Button("📷 Webcam (OpenCV)")
                conf = gr.Slider(0.1, 0.9, value=0.35, step=0.05, label="Confidence threshold")
                portion = gr.Slider(0.5, 2.0, value=1.0, step=0.1, label="Portion correction (×)")
                denoise = gr.Checkbox(False, label="SCUNet denoising (experimental, +~0.5 s)")
                run_btn = gr.Button("Analyze", variant="primary")
            with gr.Column():
                out_img = gr.Image(label="Recognized components")
                total = gr.Markdown()
        table = gr.Dataframe(headers=COLUMNS, label="Components", interactive=False)
        with gr.Row():
            meal = gr.Textbox(label="Meal name (for saving)", scale=3)
            save_btn = gr.Button("Save to training data", scale=1)
        status = gr.Markdown()

        cam_btn.click(from_camera, outputs=img).then(analyze, [img, conf, portion, denoise], [out_img, table, total])
        run_btn.click(analyze, [img, conf, portion, denoise], [out_img, table, total])
        portion.release(analyze, [img, conf, portion, denoise], [out_img, table, total])
        save_btn.click(save, [img, meal, table], status)
    return demo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--open-browser", action="store_true")
    args = ap.parse_args()
    if sys.stdout is None:  # started with pythonw (from the tray): no console, log to a file instead
        sys.stdout = sys.stderr = open(ROOT / "runs/app.log", "a", encoding="utf-8", buffering=1)
    demo = build(args.weights or default_weights(), args.camera)
    demo.launch(server_name="127.0.0.1", server_port=args.port, inbrowser=args.open_browser)


if __name__ == "__main__":
    main()
