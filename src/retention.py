"""Keeps only the last KEEP_DAYS days (today included) of what food-cal collects in everyday use; anything older
is deleted for good. The tray service runs this at start and after every midnight.

Deleted when older: diary rows (data/diary.csv), scan photos (data/webcam/raw/*_scan), voice logs (data/voice),
lines of the service log (runs/scan_service.log*).
Kept: photos saved on purpose as training data (data/webcam/raw/*_meal — rename a *_scan folder to *_meal to
keep it), datasets and models.

    python src/retention.py      # clean up now
"""
import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import diary

ROOT = Path(__file__).resolve().parents[1]
KEEP_DAYS = 4

log = logging.getLogger("food-cal")


def _day(name: str) -> date | None:
    """Date from a name that starts with YYYYMMDD (scan folders, voice logs); None if it does not."""
    try:
        return datetime.strptime(name[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _prune_log(path: Path, keep_from: date) -> int:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    keep, current = [], True
    for line in lines:
        try:
            current = datetime.strptime(line[:10], "%Y-%m-%d").date() >= keep_from
        except ValueError:
            pass  # a traceback line goes with the entry above it
        if current:
            keep.append(line)
    if len(keep) < len(lines):
        path.write_text("".join(keep), encoding="utf-8")  # the service's log handler appends, so this is safe
    return len(lines) - len(keep)


def prune(days: int = KEEP_DAYS) -> dict:
    keep_from = date.today() - timedelta(days=days - 1)
    done = {"scans": 0, "voice logs": 0, "diary rows": 0, "log lines": 0}

    old = [d for d in (ROOT / "data/webcam/raw").glob("*_scan") if d.is_dir() and (_day(d.name) or keep_from) < keep_from]
    for d in old:
        try:
            shutil.rmtree(d)
            done["scans"] += 1
        except OSError as e:
            log.warning(f"Cleanup: {d.name} not deleted ({e})")
    for f in (ROOT / "data/voice").glob("*"):
        if f.is_file() and (_day(f.name) or keep_from) < keep_from:
            try:
                f.unlink()
                done["voice logs"] += 1
            except OSError as e:
                log.warning(f"Cleanup: {f.name} not deleted ({e})")
    try:
        done["diary rows"] = diary.prune(keep_from)
    except OSError as e:
        log.warning(f"Cleanup: diary not pruned ({e}) - is it open in Excel?")
    for f in (ROOT / "runs").glob("scan_service.log*"):
        try:
            done["log lines"] += _prune_log(f, keep_from)
        except OSError as e:
            log.warning(f"Cleanup: {f.name} not pruned ({e})")

    if any(done.values()):
        log.info(f"Cleanup (kept {keep_from} onwards): " + ", ".join(f"{v} {k}" for k, v in done.items() if v))
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(prune())
