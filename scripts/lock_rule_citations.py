"""Verify warehouse/seeds/rule_citations.csv at its stated locations and write the file-hash lock.

    uv run python scripts/lock_rule_citations.py

Run after a person edits the citation seed. It fails (no lock written) if any quote is not in its stated file, a
page number does not match, or a required claim role / period action is not covered.
"""

from tariffagent.answer.citations import LOCK, REPO, check_coverage, load_verified, write_lock

if __name__ == "__main__":
    n = write_lock()
    check_coverage(load_verified())
    print(f"wrote {LOCK.relative_to(REPO).as_posix()} ({n} files)")
