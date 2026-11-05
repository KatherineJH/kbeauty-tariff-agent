"""Shared helpers for collectors: polite HTTP GET, raw archiving, manifest rows.

Every collector stores the response body byte-for-byte under data/raw/<source>/ and appends one row per file to
data/raw/<source>/manifest.csv (url, retrieved_at UTC, file, bytes, sha256). No API keys are used by these sources.
"""

import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
USER_AGENT = "kbeauty-tariff-agent/0.1 (research portfolio project; polite single-threaded collector)"
DELAY_SECONDS = 1.5
MANIFEST_FIELDS = ["url", "retrieved_at", "file", "bytes", "sha256"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(url: str, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
            time.sleep(DELAY_SECONDS)
            return body
        except Exception as exc:  # network errors are retried, then raised
            last = exc
            time.sleep(DELAY_SECONDS * (attempt + 2))
    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last


def archive(source: str, filename: str, url: str, body: bytes) -> dict:
    out_dir = RAW / source
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_bytes(body)
    row = {"url": url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "file": path.relative_to(REPO).as_posix(), "bytes": len(body), "sha256": sha256(body)}
    manifest = out_dir / "manifest.csv"
    new = not manifest.exists()
    with manifest.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow(row)
    print(f"saved {row['file']} ({row['bytes']} bytes)")
    return row
