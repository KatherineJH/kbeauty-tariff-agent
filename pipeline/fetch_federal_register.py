"""Collect Federal Register documents (D4) from the official REST API (no API key).

    uv run python pipeline/fetch_federal_register.py

1. The searches used to choose documents are archived as-is (evidence for the selection).
2. For each document in pipeline/fr_documents.csv: the full API record (JSON) and the body as served by raw_text_url (GPO HTML with a <pre> text block).

Selection rule (fixed before reading any document body): presidential documents and agency documents published
from 2025-01-01 that set, modify, end or implement (a) the reciprocal tariffs or other additional tariffs applying to Korea or to all
countries, (b) the de minimis suspension, (c) IEEPA refunds, or (d) Section 301 actions on multiple economies.
Documents specific to another single country (China, Brazil, Japan, UK, ...) are excluded.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import archive, get  # noqa: E402

API = "https://www.federalregister.gov/api/v1"
LIST = Path(__file__).resolve().parent / "fr_documents.csv"
SUMMARY = ("fields[]=document_number&fields[]=title&fields[]=publication_date&fields[]=type"
           "&fields[]=executive_order_number&fields[]=agencies&per_page=100")
SEARCHES = {
    "search_presidential_reciprocal.json":
        "conditions[type][]=PRESDOCU&conditions[term]=reciprocal%20tariff&conditions[publication_date][gte]=2025-01-01",
    "search_cbp_de_minimis.json":
        "conditions[term]=%22de%20minimis%22&conditions[publication_date][gte]=2025-01-01"
        "&conditions[agencies][]=u-s-customs-and-border-protection",
    "search_korea_reciprocal.json":
        "conditions[term]=Korea%20reciprocal&conditions[publication_date][gte]=2025-07-01",
    # Added 2026-11-05: EO 14389 sec. 2(c) names the 2026-02-20 import-surcharge proclamation, which the three
    # searches above missed. It falls under rule (a) (tariffs applying to all countries).
    "search_presidential_surcharge.json":
        "conditions[type][]=PRESDOCU&conditions[term]=surcharge&conditions[publication_date][gte]=2026-01-01",
}


def main() -> None:
    for name, query in SEARCHES.items():
        url = f"{API}/documents.json?{query}&{SUMMARY}"
        archive("federal_register", name, url, get(url))
    with LIST.open(encoding="utf-8") as f:
        numbers = [row["document_number"] for row in csv.DictReader(f)]
    for num in numbers:
        url = f"{API}/documents/{num}.json"
        body = get(url)
        archive("federal_register", f"doc_{num}.json", url, body)
        text_url = json.loads(body).get("raw_text_url")
        if not text_url:
            sys.exit(f"no raw_text_url for {num}")
        archive("federal_register", f"doc_{num}.html", text_url, get(text_url))


if __name__ == "__main__":
    main()
