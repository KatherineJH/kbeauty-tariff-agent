"""Rehydrate and verify the archived HTS revisions (D2a), whose PDFs and full page texts are not committed.

    uv run python scripts/rehydrate_hts_archive.py --check      # offline: committed evidence is self-consistent
    uv run python scripts/rehydrate_hts_archive.py              # network: re-download missing PDFs, verify, re-extract
    uv run python scripts/rehydrate_hts_archive.py --write-sums # after an intended change: rewrite LOGICAL_SHA256SUMS

Three levels of reproducibility (docs/architecture.md, section 5):
1. committed evidence -> regulatory table: offline (--check and the test suite).
2. official PDFs -> evidence: needs the network; PDFs are re-downloaded from the URLs in each manifest and must match
   the recorded SHA-256 before extraction; the re-extracted outputs must match LOGICAL_SHA256SUMS.
3. the PDFs themselves: their long-term availability depends on the USITC archive.
"""

import argparse
import csv
import subprocess
import sys
import tempfile
import urllib.request
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "hts_archive"
EXTRACTED = REPO / "data" / "extracted"
SUMS = EXTRACTED / "hts_archive" / "LOGICAL_SHA256SUMS"
USER_AGENT = "kbeauty-tariff-agent/0.1 (research portfolio project; polite single-threaded collector)"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def logical_files(root: Path) -> list[Path]:
    """Committed comparison outputs whose content defines the extraction result."""
    base = root / "hts_archive"
    files = [base / n for n in ("heading_presence.csv", "heading_context.csv", "cosmetics_mentions.csv",
                                "change_records.csv")]
    for rel in sorted(p for p in base.iterdir() if p.is_dir()):
        files += [rel / "pages.csv", rel / "change_record.txt"]
    files.append(root / "hts_archive_evidence" / "evidence_index.csv")
    files += sorted((root / "hts_archive_evidence").glob("*/page_*.txt"))
    return files


def current_sums(root: Path) -> dict[str, str]:
    return {f.relative_to(root).as_posix(): digest(f) for f in logical_files(root)}


def check_committed() -> list[str]:
    problems = []
    expected = dict(reversed(line.split("  ", 1)) for line in SUMS.read_text(encoding="utf-8").splitlines() if line)
    actual = current_sums(EXTRACTED)
    problems += [f"logical hash differs: {k}" for k in expected if actual.get(k) != expected[k]]
    problems += [f"not in LOGICAL_SHA256SUMS: {k}" for k in actual if k not in expected]
    with (EXTRACTED / "hts_archive_evidence" / "evidence_index.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            with (EXTRACTED / "hts_archive" / row["release"] / "pages.csv").open(encoding="utf-8") as g:
                page_hash = {r["page"]: r["text_sha256"] for r in csv.DictReader(g)}
            if page_hash.get(row["pdf_page"]) != row["text_sha256"]:
                problems.append(f"evidence page hash differs from pages.csv: {row['release']} p{row['pdf_page']}")
    return problems


def rehydrate() -> list[str]:
    problems = []
    for manifest in sorted(RAW.glob("*/manifest.csv")):
        with manifest.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                path = REPO / row["file"]
                if not path.exists():
                    req = urllib.request.Request(row["url"], headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        path.write_bytes(resp.read())
                    print(f"downloaded {row['file']}")
                if digest(path) != row["sha256"]:
                    problems.append(f"raw hash differs from manifest: {row['file']}")
    if problems:
        return problems
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        subprocess.run([sys.executable, str(REPO / "pipeline" / "extract_hts_archive.py"), "--out", str(tmp)],
                       check=True)
        subprocess.run([sys.executable, str(REPO / "pipeline" / "build_hts_archive_evidence.py"), "--src", str(tmp),
                        "--out", str(tmp)], check=True, cwd=REPO / "pipeline")
        expected = dict(reversed(l.split("  ", 1)) for l in SUMS.read_text(encoding="utf-8").splitlines() if l)
        actual = current_sums(tmp)
        problems += [f"re-extracted output differs: {k}" for k in expected if actual.get(k) != expected[k]]
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write-sums", action="store_true")
    args = parser.parse_args()
    if args.write_sums:
        lines = [f"{h}  {k}" for k, h in sorted(current_sums(EXTRACTED).items())]
        SUMS.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        print(f"wrote {SUMS.relative_to(REPO)} ({len(lines)} files)")
        return
    problems = check_committed() if args.check else rehydrate()
    if problems:
        sys.exit("\n".join(problems))
    print("ok")


if __name__ == "__main__":
    main()
