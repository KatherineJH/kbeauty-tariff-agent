"""Structure the code-level exception lists of HTS chapter 99 that matter for Korean cosmetics (offline).

    uv run python pipeline/extract_hts_exceptions.py [--out DIR]

Reads the page texts written by extract_hts_pdf.py (data/extracted/hts_pdf/chapter_99/page_NNNN.txt).

Two regimes:
- surcharge  : sec. 122 surcharge, heading 9903.03.01, U.S. note 2(aa) to subchapter III
- s301_korea : section 301 tariffs on products of South Korea, headings 9903.05.70-9903.05.71, U.S. note 52

Outputs:
  <out>/hts_exception_lists.csv   one row per subdivision: regime, subdivision, exempting heading, kind
                                  (code_list | particular_articles | descriptive), pages, code count, note
  <out>/hts_exception_codes.csv   one row per listed HTS code: regime, subdivision, code, digits, pdf page
  <out>/cosmetics_exception_check.csv
                                  every chapter 33 code under headings 3303-3307 in data/raw/hts/export_ch33.json
                                  checked for exact equality of its 8-digit subheading with a listed code

Determinations (as of HTS Revision 22 only; earlier revisions are not checked):
  explicit_exclusion                    the 8-digit subheading is printed in a code list of the regime
  needs_review_232_aluminum_derivative  not in the regime's lists, but listed in U.S. note 19(k) (232 duty on the
                                        aluminum content of derivative products); how the regime treats that content
                                        at the relevant date is not settled by the corpus
  not_excepted_rev22                    not in any code list of the regime and not a 19(k) derivative; descriptive
                                        exceptions do not name chapter 33

pdf_page is the physical 1-based page index of data/raw/hts/chapter_99.pdf; printed_page is the label printed on it.

Matching rule: a code is excluded only when its 8-digit subheading is printed in a list that says the duty "shall not
apply to articles ... classifiable in the following subheadings/provisions". No prefix or heading-level inference.
pypdf prints each row of the five-column lists right to left; the lists are treated as sets, so order is irrelevant
(checked against the rendered pages 224 and 568).
"""

import argparse
import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGES = REPO / "data" / "extracted" / "hts_pdf" / "chapter_99"
CH33 = REPO / "data" / "raw" / "hts" / "export_ch33.json"
DEFAULT_OUT = REPO / "data" / "extracted"

# An HTS code as printed: 4.2.2 digits, optionally followed by a 2-digit statistical suffix. Codes in the lists are
# printed without separators, so a code ends where the next code (4 digits and a dot) or a non-digit begins.
CODE = re.compile(r"(\d{4}\.\d{2}\.\d{2}(?:\d{2})?)(?=\d{4}\.\d{2}|\D|$)")
BOILERPLATE = re.compile(r"^(Harmonized Tariff Schedule of the United States.*|Annotated for Statistical Reporting "
                         r"Purposes|XXII|99 - III - \d+|U\.S\. Notes \(con\.\))$")

# (regime, subdivision, exempting heading, kind, first page, last page, start marker, end marker, note)
SUBDIVISIONS = [
    ("surcharge", "2(aa)(ii)", "9903.03.03", "code_list", 223, 227,
     r"^\(ii\) As provided in heading 9903\.03\.03", r"^\(iii\) As provided in heading 9903\.03\.04", ""),
    ("surcharge", "2(aa)(iii)", "9903.03.04", "particular_articles", 227, 227,
     r"^\(iii\) As provided in heading 9903\.03\.04", r"^Harmonized Tariff Schedule", ""),
    ("surcharge", "2(aa)(iv)", "9903.03.05", "code_list", 228, 230,
     r"^\(iv\) As provided in heading 9903\.03\.05", r"^\(v\) As provided in heading 9903\.03\.06",
     "civil aircraft meeting general note 6 criteria"),
    ("surcharge", "2(aa)(v)", "9903.03.06", "descriptive", 230, 231, None, None,
     "goods in section 232 / pharmaceutical / vehicle / wood / semiconductor headings of chapter 99; text modified "
     "after expiration by 91 Fed. Reg. 18183 (not in the corpus)"),
    ("surcharge", "2(aa)(vi)", "9903.03.07", "descriptive", 231, 231, None, None, "products of Canada under USMCA"),
    ("surcharge", "2(aa)(vii)", "9903.03.08", "descriptive", 231, 231, None, None, "products of Mexico under USMCA"),
    ("surcharge", "2(aa)(viii)", "9903.03.09", "descriptive", 231, 231, None, None,
     "CAFTA-DR textile or apparel goods"),
    ("s301_korea", "52(b)", "9903.05.86", "code_list", 566, 569,
     r"^\(b\) As provided in heading 9903\.05\.86", r"^\(c\) As provided in heading 9903\.05\.87", ""),
    ("s301_korea", "52(c)", "9903.05.87", "particular_articles", 569, 571,
     r"^\(c\) As provided in heading 9903\.05\.87", r"^\(d\) As provided in heading 9903\.05\.88", ""),
    ("s301_korea", "52(d)", "9903.05.88", "code_list", 571, 574,
     r"^\(d\) As provided in heading 9903\.05\.88", r"^\(e\) As provided in heading 9903\.05\.89",
     "civil aircraft meeting general note 6 criteria"),
    ("s301_korea", "52(e)", "9903.05.89", "code_list", 574, 577,
     r"^\(e\) As provided in heading 9903\.05\.89", r"^\(f\) As provided in heading 9903\.05\.90",
     "articles for use in pharmaceutical applications"),
    ("s301_korea", "52(f)", "9903.05.90", "descriptive", 577, 577, None, None,
     "section 232 metals, vehicles and parts, wood, semiconductors, patented pharmaceuticals (chapter 99 headings)"),
    ("s301_korea", "52(g)-(i)", "9903.05.93-9903.05.95", "descriptive", 577, 577, None, None,
     "apply only to headings for Canada, Mexico and CAFTA-DR countries, not to 9903.05.70-9903.05.71"),
    ("s232_aluminum_derivative", "19(k)", "9903.85.08", "code_list", 256, 256,
     r"^\(k\) The rates of duty in heading 9903\.85\.08", r"^For any derivative aluminum product",
     "derivative aluminum products of all countries other than the UK; the 232 duty applies only to the declared "
     "value of the aluminum content"),
    ("s301_korea", "52(j)", "9903.05.96-9903.06.21", "descriptive", 578, 605, None, None,
     "country-specific lists; each names the heading it limits (9903.05.22, .26, .28, .35, .37, .40, .45, .50, .54, "
     ".75-.76, .81) and none names 9903.05.70 or 9903.05.71"),
]


def printed_label(page: int) -> str:
    """The page label printed on the PDF page (e.g. '99-III-52'); pdf_page is the physical 1-based index."""
    text = (PAGES / f"page_{page:04d}.txt").read_text(encoding="utf-8")
    m = re.search(r"99 - ([IVX]+) - (\d+)", text)
    return f"99-{m.group(1)}-{m.group(2)}" if m else ""


def page_lines(page: int) -> list[str]:
    text = (PAGES / f"page_{page:04d}.txt").read_text(encoding="utf-8")
    return [line for line in text.split("\n") if not BOILERPLATE.match(line.strip())]


def collect(first: int, last: int, start: str, end: str) -> list[tuple[str, int]]:
    codes, active = [], False
    for page in range(first, last + 1):
        for line in page_lines(page):
            if not active and re.search(start, line):
                active = True
                continue
            if active and re.search(end, line) and not re.search(start, line):
                return codes
            if active:
                codes.extend((code, page) for code in CODE.findall(line))
    if not active:
        raise SystemExit(f"start marker not found: {start}")
    return codes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--offline", action="store_true", help="accepted for symmetry; never uses the network")
    args = parser.parse_args()

    list_rows, code_rows = [], []
    listed: dict[str, dict[str, list[str]]] = {"surcharge": {}, "s301_korea": {}, "s232_aluminum_derivative": {}}
    for regime, sub, heading, kind, first, last, start, end, note in SUBDIVISIONS:
        found = collect(first, last, start, end) if kind != "descriptive" else []
        # (aa)(iii) ends at the page footer, which BOILERPLATE removes; stop at the next subdivision instead.
        if sub == "2(aa)(iii)":
            found = collect(first, last, start, r"^\(iv\) As provided")
        seen = set()
        for code, page in found:
            if code in seen:
                continue
            seen.add(code)
            code_rows.append({"regime": regime, "subdivision": sub, "exempting_heading": heading, "code": code,
                              "digits": len(code.replace(".", "")), "pdf_page": page,
                              "printed_page": printed_label(page)})
            listed[regime].setdefault(code[:10], []).append(sub)
        list_rows.append({"regime": regime, "subdivision": sub, "exempting_heading": heading, "kind": kind,
                          "pdf_pages": f"{first}-{last}",
                          "printed_pages": f"{printed_label(first)} to {printed_label(last)}", "codes": len(seen),
                          "note": note})

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "hts_exception_lists.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(list_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(list_rows)
    with (args.out / "hts_exception_codes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(code_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(code_rows)

    ch33 = json.loads(CH33.read_text(encoding="utf-8"))
    checks = []
    for item in ch33:
        htsno = item.get("htsno") or ""
        if not re.match(r"^330[3-7]\.\d{2}\.\d{2}", htsno):
            continue
        sub8 = htsno[:10]
        aluminum = bool(listed["s232_aluminum_derivative"].get(sub8))
        for regime in ("surcharge", "s301_korea"):
            subs = listed[regime].get(sub8, [])
            if subs:
                determination = "explicit_exclusion"
            elif aluminum:
                determination = "needs_review_232_aluminum_derivative"
            else:
                determination = "not_excepted_rev22"
            checks.append({"htsno": htsno, "subheading_8": sub8, "description": item.get("description"),
                           "regime": regime, "determination": determination, "listed_in": "; ".join(subs),
                           "aluminum_232_derivative_19k": aluminum})
    with (args.out / "cosmetics_exception_check.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(checks)
    counts = {d: sum(c["determination"] == d for c in checks) for d in sorted({c["determination"] for c in checks})}
    print(f"extract  {len(code_rows)} listed codes in {len(list_rows)} subdivisions; cosmetics checks {counts}")


if __name__ == "__main__":
    main()
