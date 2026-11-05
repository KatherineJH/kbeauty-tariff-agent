"""Re-running the offline extractors reproduces the committed extracted files exactly (normalized content).

The full chapter 99 PDF (818 pages, about 2 minutes) is left to a manual rerun; here the smaller PDFs are re-extracted
and compared page by page, and the Federal Register and exception-list extractors are re-run in full.
"""

import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXTRACTED = REPO / "data" / "extracted"
SMALL_PDFS = ["chapter_33.pdf", "general_note_33.pdf", "general_rules_of_interpretation.pdf"]


def run(script: str, out: Path, *extra: str) -> None:
    subprocess.run([sys.executable, str(REPO / "pipeline" / script), "--out", str(out), *extra], check=True,
                   capture_output=True)


def same_tree(a: Path, b: Path) -> list[str]:
    diffs = [p.relative_to(a).as_posix() for p in sorted(a.rglob("*")) if p.is_file()
             and (not (b / p.relative_to(a)).exists() or (b / p.relative_to(a)).read_bytes() != p.read_bytes())]
    return diffs


def test_federal_register_extraction_is_reproducible(tmp_path):
    run("extract_federal_register.py", tmp_path)
    assert (tmp_path / "fr_documents.csv").read_bytes() == (EXTRACTED / "fr_documents.csv").read_bytes()
    assert not same_tree(tmp_path / "fr_text", EXTRACTED / "fr_text")


def test_pdf_page_extraction_is_reproducible(tmp_path):
    run("extract_hts_pdf.py", tmp_path, "--only", *SMALL_PDFS)
    stems = [Path(n).stem for n in SMALL_PDFS]
    for stem in stems:
        assert not same_tree(tmp_path / "hts_pdf" / stem, EXTRACTED / "hts_pdf" / stem), stem
    with (tmp_path / "hts_pdf" / "pages.csv").open(encoding="utf-8") as f:
        rebuilt = list(csv.DictReader(f))
    with (EXTRACTED / "hts_pdf" / "pages.csv").open(encoding="utf-8") as f:
        committed = [r for r in csv.DictReader(f) if r["stem"] in stems]
    assert rebuilt == committed


def test_exception_list_extraction_is_reproducible(tmp_path):
    run("extract_hts_exceptions.py", tmp_path)
    for name in ("hts_exception_lists.csv", "hts_exception_codes.csv", "cosmetics_exception_check.csv"):
        assert (tmp_path / name).read_bytes() == (EXTRACTED / name).read_bytes(), name
