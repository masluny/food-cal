"""Food diary: what you ate, one row per meal, in data/diary.csv (opens in Excel / Notepad).

Used by the tray service: "ADD TODAY" on the display appends the last scan, the Today screen shows the
sum for the current date, EDIT on the display lists today's meals and deletes them, "Undo last add" in the
tray menu removes the newest row.
"""
import csv
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/diary.csv"
FIELDS = ["date", "time", "name", "kcal", "protein", "fat", "carbs", "grams", "scan"]
MACROS = ("kcal", "protein", "fat", "carbs")


def _rows() -> list[dict]:
    if not PATH.exists():
        return []
    with PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write(rows: list[dict]):
    with PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def add(name: str, kcal: float, protein: float, fat: float, carbs: float, grams: float, scan: str = "") -> dict:
    now = datetime.now()
    row = {"date": now.date().isoformat(), "time": now.strftime("%H:%M"), "name": name, "kcal": round(kcal),
           "protein": round(protein, 1), "fat": round(fat, 1), "carbs": round(carbs, 1), "grams": round(grams),
           "scan": scan}
    new = not PATH.exists()
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    return row


def today_rows() -> list[dict]:
    today = date.today().isoformat()
    return [r for r in _rows() if r["date"] == today]


def delete(time: str, name: str, kcal: str) -> dict | None:
    """Removes the newest of today's rows with this time, name and kcal; returns it (None if not found)."""
    rows = _rows()
    today = date.today().isoformat()
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        if r["date"] == today and r["time"] == time and r["name"] == name and str(r["kcal"]) == str(kcal):
            removed = rows.pop(i)
            _write(rows)
            return removed
    return None


def undo_last_today() -> dict | None:
    """Removes the newest row from today; returns it (None if today is empty)."""
    rows = today_rows()
    return delete(rows[-1]["time"], rows[-1]["name"], rows[-1]["kcal"]) if rows else None


def prune(keep_from: date) -> int:
    """Deletes the rows dated before keep_from (src/retention.py); returns how many."""
    rows = _rows()
    keep = [r for r in rows if r["date"] >= keep_from.isoformat()]
    if len(keep) < len(rows):
        _write(keep)
    return len(rows) - len(keep)


def totals(day: date | None = None) -> dict:
    day = (day or date.today()).isoformat()
    rows = [r for r in _rows() if r["date"] == day]
    out = {k: round(sum(float(r[k] or 0) for r in rows), 1) for k in MACROS}
    out["meals"] = len(rows)
    out["last"] = f"{rows[-1]['name']} +{rows[-1]['kcal']} kcal" if rows else ""
    return out
