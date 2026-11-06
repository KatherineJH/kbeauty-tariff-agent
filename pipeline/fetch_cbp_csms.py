"""Collect selected CBP Cargo Systems Messaging Service (CSMS) bulletins (D4a) and extract their text.

    uv run python pipeline/fetch_cbp_csms.py            # download (network) and extract
    uv run python pipeline/fetch_cbp_csms.py --offline  # re-extract from data/raw/cbp_csms only

Scope (docs/data_sources.md, D4a): only CBP guidance on when IEEPA duty collection ended under EO 14389.
Raw HTML is kept byte-for-byte in data/raw/cbp_csms/ with a manifest; the bulletin body text is written, normalized,
to data/extracted/cbp_csms/<csms_number>.txt.
"""

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, archive, get  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BULLETINS = {  # CSMS number: official CBP bulletin URL on GovDelivery
    "67834313": "https://content.govdelivery.com/accounts/USDHSCBP/bulletins/40b11c9",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")]
    out = "\n".join(line for line in lines if line)
    return out + "\n"


def body_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</tr>|</div>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    start = text.find("CSMS #")
    end = text.find("Subscribe to updates")
    return normalize(text[start:end if end > start else None])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    out = REPO / "data" / "extracted" / "cbp_csms"
    out.mkdir(parents=True, exist_ok=True)
    for number, url in BULLETINS.items():
        raw_path = RAW / "cbp_csms" / f"csms_{number}.html"
        if not args.offline:
            archive("cbp_csms", raw_path.name, url, get(url))
        text = body_text(raw_path.read_text(encoding="utf-8"))
        (out / f"{number}.txt").write_bytes(text.encode("utf-8"))
        print(f"extract  CSMS {number}: {len(text)} chars")


if __name__ == "__main__":
    main()
