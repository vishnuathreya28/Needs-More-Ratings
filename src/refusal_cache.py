"""
Remember posts Grok declined (or whose drafts our checks blocked), so later runs do not pay to research them again right away.

Stored in refusals.json at the repo root (gitignored). Entries expire so a post can be
re-checked once new evidence may exist:
  NO NOTE NEEDED       after REFUSAL_TTL_NO_NOTE_DAYS (default 7)
  NOT ENOUGH EVIDENCE  after REFUSAL_TTL_NOT_ENOUGH_DAYS (default 2)
  BLOCKED              after REFUSAL_TTL_BLOCKED_DAYS (default 3): a draft was written but our checks
                       (length, URL, emoji, ClaimOpinion cutoff) held it back
Pass --recheck-refusals to main.py to ignore the file for one run.
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent / "refusals.json"
_lock = threading.Lock()
BLOCKED = "BLOCKED"


def _ttl(decision: str) -> timedelta:
    if decision == BLOCKED:
        return timedelta(days=float(os.getenv("REFUSAL_TTL_BLOCKED_DAYS", "3")))
    if decision == "NOT ENOUGH EVIDENCE":
        return timedelta(days=float(os.getenv("REFUSAL_TTL_NOT_ENOUGH_DAYS", "2")))
    return timedelta(days=float(os.getenv("REFUSAL_TTL_NO_NOTE_DAYS", "7")))


def load() -> dict:
    """Return {post_id: {"decision", "at"}} with expired entries dropped."""
    try:
        data = json.loads(CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    now = datetime.now(timezone.utc)
    return {
        pid: e
        for pid, e in data.items()
        if now - datetime.fromisoformat(e["at"]) < _ttl(e["decision"])
    }


def record(cache: dict, post_id: str, decision: str) -> None:
    with _lock:
        cache[str(post_id)] = {"decision": decision, "at": datetime.now(timezone.utc).isoformat()}


def save(cache: dict) -> None:
    with _lock:
        CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True))
