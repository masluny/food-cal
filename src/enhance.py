"""Image enhancement models (spandrel): SCUNet — denoising, Real-ESRGAN x2 — super-resolution.

Simulated-webcam test (runs/robustness_*.json, 2026-10-12): they recover ~1/3 of the loss on FoodSeg103,
±0 on Food-101, and some classes get worse. On a real webcam frame SCUNet turned toasts into "sweets".
So this is an option (--denoise / checkbox in the app), not a default step.
"""
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
ENHANCERS = {
    "scunet": ROOT / "models/enhance/scunet_color_real_psnr.pth",
    "esrgan": ROOT / "models/enhance/RealESRGAN_x2plus.pth",
}


class Enhancer:
    def __init__(self, path: Path, tile: int = 384, overlap: int = 32):
        from spandrel import ModelLoader
        self.model = ModelLoader().load_from_file(path).cuda().eval()
        self.scale, self.tile, self.overlap = self.model.scale, tile, overlap

    @torch.no_grad()
    def __call__(self, bgr: np.ndarray) -> np.ndarray:
        x = torch.from_numpy(bgr[..., ::-1].copy()).permute(2, 0, 1)[None].float().div(255).cuda()
        _, _, h, w = x.shape
        out = torch.zeros(1, 3, h * self.scale, w * self.scale, device="cuda")
        weight = torch.zeros_like(out)
        step = self.tile - self.overlap
        for y in range(0, max(h - self.overlap, 1), step):
            for xx in range(0, max(w - self.overlap, 1), step):
                y0, x0 = min(y, max(h - self.tile, 0)), min(xx, max(w - self.tile, 0))
                patch = x[..., y0:y0 + self.tile, x0:x0 + self.tile]
                res = self.model(patch).clamp(0, 1)
                s = self.scale
                out[..., y0 * s:(y0 + patch.shape[2]) * s, x0 * s:(x0 + patch.shape[3]) * s] += res
                weight[..., y0 * s:(y0 + patch.shape[2]) * s, x0 * s:(x0 + patch.shape[3]) * s] += 1
        img = (out / weight).squeeze(0).permute(1, 2, 0).mul(255).round().byte().cpu().numpy()[..., ::-1]
        if self.scale != 1:  # back to the input size — the detector gets 640 px anyway
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        return np.ascontiguousarray(img)
