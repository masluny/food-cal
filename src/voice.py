"""Voice input: microphone -> text (faster-whisper, locally on the CPU) -> language model -> dish, kcal, macros.

Used by the tray service while you hold the microphone button on the display. Only the transcribed text is
sent out: to Google Gemini first, to an OpenRouter model if Gemini fails (configs/voice.yaml: provider, fallback);
the audio never leaves the PC. Keys: configs/secrets.yaml.

    python src/voice.py "two cheese toasts with ham"    # test the model part without the microphone
"""
import json
import logging
import sys
import threading
import time
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import yaml
from scipy.signal import resample_poly

# PortAudio starts with `import sounddevice` and would hold on to every audio device for as long as the service
# runs: unplugging the Focusrite then made Windows add and remove it in Settings > Sound over and over until the
# service quit. So it runs only while recording (Recorder.start .. stop), with a fresh device list each time.
sd._terminate()

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("food-cal")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
SYSTEM = """You estimate the nutrition of a meal from a short spoken description. The text was transcribed
automatically from speech (often Polish), so expect small recognition errors.
List EVERY food and drink mentioned as a separate item with its quantity (e.g. "dwa"/"two" = 2 pieces).
When amounts are not given, assume typical Polish home portions. Values of each item are for its whole
quantity, not per piece. Answer with ONE JSON object and nothing else:
{"name": "short ENGLISH name of the whole meal (translate it), ASCII only, max 22 characters",
 "items": [{"name": "English name", "qty": 1, "grams": 0, "kcal": 0, "protein": 0, "fat": 0, "carbs": 0}],
 "uncertainty": 0.3}
protein, fat and carbs are in grams; uncertainty is the relative error of the total kcal (0.1 = sure,
0.5 = rough guess). If the text does not describe food, answer {"error": "not food"}.
Use these reference values when an item matches (same numbers as the camera scanner uses)."""

# typical portions of the dishes from configs/classes.yaml (what "one" means when no amount is said)
PORTIONS = {
    "toast": "1 toasted sandwich (2 slices of toast bread, cheese, ham) = 95 g",
    "zapiekanka": "1 zapiekanka (half baguette, mushrooms, cheese) = 300 g",
    "pizza": "1 slice = 110 g, whole 30 cm pizza = 500 g",
    "bread": "1 slice = 30 g, 1 roll = 60 g",
    "pasta": "1 plate cooked = 300 g",
    "rice": "1 portion cooked = 200 g",
    "potatoes": "1 portion boiled = 250 g",
    "fries": "1 portion = 150 g",
    "breaded_cutlet": "1 kotlet schabowy = 150 g",
    "meat": "1 portion = 150 g",
    "chicken": "1 breast fillet = 170 g",
    "sausage": "1 portion = 100 g",
    "fish": "1 fillet = 150 g",
    "egg": "1 egg = 55 g",
    "soup": "1 bowl = 350 g",
    "salad": "1 portion = 150 g",
    "drink": "1 glass = 250 ml",
    "burger": "1 cheeseburger = 120 g, Big Mac = 215 g, Whopper = 270 g",
    "hot_dog": "1 hot dog in a bun = 110 g",
    "burrito": "1 burrito = 230 g",
    "dumplings": "1 pieróg = 33 g, a plate (8 pierogi) = 270 g",
    "coffee_tea": "1 mug = 250 ml (black coffee or tea alone = 2 kcal; milk and sugar add the rest)",
    "milk_drink": "1 glass = 250 ml",
}


def system_prompt() -> str:
    nutrition = yaml.safe_load((ROOT / "configs/nutrition.yaml").read_text(encoding="utf-8"))
    rows = [f"- {k.replace('_', ' ')}: {v['kcal']} kcal, P {v['protein']} g, F {v['fat']} g, C {v['carbs']} g "
            f"per 100 g" + (f"; {PORTIONS[k]}" if k in PORTIONS else "") for k, v in nutrition.items() if k != "other"]
    return SYSTEM + "\n" + "\n".join(rows)


def load_cfg() -> dict:
    return yaml.safe_load((ROOT / "configs/voice.yaml").read_text(encoding="utf-8"))


def find_device(name: str | None) -> int | None:
    if not name:
        return None  # Windows default input
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and name.lower() in d["name"].lower():
            return i
    return None


class Recorder:
    """Records from the microphone in the background until stop(); returns 16 kHz mono audio."""

    def __init__(self, device: str | None = None):
        self.name = device
        self.device, self.stream, self.chunks, self.sr, self.t0 = None, None, [], 16000, 0.0

    @property
    def active(self) -> bool:
        return self.stream is not None

    @property
    def seconds(self) -> float:
        return time.time() - self.t0 if self.active else 0.0

    def start(self):
        sd._initialize()  # fresh device list: also finds a mic plugged in after the service started
        try:
            self.device = find_device(self.name)
            self.chunks = []
            self.sr = int(sd.query_devices(self.device, "input")["default_samplerate"])
            self.stream = sd.InputStream(device=self.device, samplerate=self.sr, channels=1, dtype="float32",
                                         callback=lambda data, frames, t, status: self.chunks.append(data.copy()))
            self.stream.start()
        except Exception:
            self._release()
            raise
        self.t0 = time.time()

    def _release(self):
        """Closes the stream and stops PortAudio, so no audio device is held between recordings."""
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        finally:
            self.stream = None
            sd._last_callback = None  # its exit handler would otherwise touch the closed stream
            sd._terminate()

    def stop(self) -> np.ndarray:
        if self.stream is None:
            return np.zeros(0, np.float32)
        self._release()
        audio = np.concatenate(self.chunks)[:, 0] if self.chunks else np.zeros(0, np.float32)
        g = np.gcd(self.sr, 16000)
        return resample_poly(audio, 16000 // g, self.sr // g).astype(np.float32)


_whisper = None
_whisper_lock = threading.Lock()


def preload(model_name: str = "small"):
    """Loads whisper (~1-2 s) — started when the mic button is pressed, so it is ready on release."""
    global _whisper
    with _whisper_lock:
        if _whisper is None:
            from faster_whisper import WhisperModel
            _whisper = WhisperModel(model_name, device="cpu", compute_type="int8",
                                    download_root=str(ROOT / "models/whisper"))
    return _whisper


def transcribe(audio16k: np.ndarray, model_name: str = "small", language: str | None = None) -> tuple[str, str]:
    segments, info = preload(model_name).transcribe(audio16k, language=language, beam_size=5, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip(), info.language


def extract_json(text: str) -> dict:
    """The first JSON object in the model's answer (tolerates code fences or text around it)."""
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON in the answer: {text[:200]!r}")


def secret(name: str) -> str:
    key = (yaml.safe_load((ROOT / "configs/secrets.yaml").read_text(encoding="utf-8")) or {}).get(name) or ""
    if not key.strip():
        raise RuntimeError(f"{name} is empty — paste it into {ROOT / 'configs/secrets.yaml'}")
    return key.strip()


def _ask_openrouter(text: str, cfg: dict) -> str:
    r = requests.post(API_URL, timeout=cfg.get("openrouter_timeout", 25),
                      headers={"Authorization": f"Bearer {secret('openrouter_api_key')}", "X-Title": "food-cal"},
                      json={"model": cfg["openrouter_model"], "temperature": 0.2,
                            # hidden reasoning: ~30 s instead of ~2 s for Nemotron, so off unless enabled
                            "reasoning": {"enabled": bool(cfg.get("reasoning", False))},
                            "messages": [{"role": "system", "content": system_prompt()},
                                         {"role": "user", "content": text}]})
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"].get("content") or ""


class Busy(RuntimeError):
    """The model is overloaded / rate limited (HTTP 429, 500, 503, 504) — worth retrying or falling back."""


def _ask_google(text: str, cfg: dict, model: str) -> str:
    """Gemini API (generateContent). Temperature stays at Google's default — recommended for Gemini 3 models."""
    r = requests.post(f"{GOOGLE_URL}/{model}:generateContent", timeout=cfg.get("google_timeout", 12),
                      headers={"x-goog-api-key": secret("google_api_key")},
                      json={"systemInstruction": {"parts": [{"text": system_prompt()}]},
                            "contents": [{"role": "user", "parts": [{"text": text}]}],
                            "generationConfig": {"responseMimeType": "application/json",
                                                 "thinkingConfig": {"thinkingLevel": cfg.get("thinking_level", "medium")}}})
    if r.status_code in (429, 500, 503, 504):
        raise Busy(f"Google {model} {r.status_code}: {r.text[:300]}")
    if r.status_code != 200:
        raise RuntimeError(f"Google {model} {r.status_code}: {r.text[:300]}")
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _ask_google_with_retries(text: str, cfg: dict, on_status=None) -> str:
    """Main model, retried with a short pause when it is overloaded; then the fallback model."""
    models = [cfg["google_model"]] * (1 + int(cfg.get("retries", 2)))
    if cfg.get("google_fallback_model"):
        models += [cfg["google_fallback_model"]] * 2
    last = None
    for attempt, model in enumerate(models):
        if attempt:
            if on_status:
                on_status("Model busy, retrying..." if model == cfg["google_model"] else "Trying a lighter model...")
            time.sleep(min(attempt, 3))
        try:
            return _ask_google(text, cfg, model)
        except Busy as e:
            last = e
    raise last


def _ask(provider: str, text: str, cfg: dict, on_status=None) -> dict:
    if provider == "google":
        answer, model = _ask_google_with_retries(text, cfg, on_status), cfg["google_model"]
    else:
        answer, model = _ask_openrouter(text, cfg), cfg["openrouter_model"]
    ans = extract_json(answer)
    ans["model"] = model
    return ans


def ask_llm(text: str, cfg: dict | None = None, on_status=None) -> dict:
    """Main provider first; on any error (HTTP error, overload, no JSON) the fallback provider.
    on_status(msg) is called while retrying, so the display can say what is going on."""
    cfg = cfg or load_cfg()
    main, backup = cfg.get("provider", "openrouter"), cfg.get("fallback")
    try:
        ans = _ask(main, text, cfg, on_status)
    except Exception as e:
        if not backup or backup == main:
            raise
        log.warning(f"Voice: {main} failed, asking {backup}: {e}")
        if on_status:
            on_status("Trying the backup model...")
        ans = _ask(backup, text, cfg, on_status)
    items = ans.get("items") or []
    for k in ("kcal", "protein", "fat", "carbs", "grams"):  # totals computed here, not trusted from the model
        ans[k] = round(sum(float(i.get(k) or 0) for i in items), 1)
    return ans


if __name__ == "__main__":
    t = time.time()
    print(json.dumps(ask_llm(" ".join(sys.argv[1:]) or "dwa tosty z serem i szynka"), indent=2, ensure_ascii=False))
    print(f"({time.time() - t:.1f} s)")
