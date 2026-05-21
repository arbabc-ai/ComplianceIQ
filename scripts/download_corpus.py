"""Download public-domain childcare regulation + guidance documents into data/raw/.

Two corpora are fetched (both public domain, freely redistributable):

1. CDC "Learn the Signs. Act Early." developmental milestone checklists —
   required tracking under Head Start + many state programs.

2. 45 CFR Part 1302 — Head Start Program Performance Standards — federal regs
   on staff qualifications, child:staff ratios, curriculum, family engagement.
   Fetched as HTML from eCFR.gov; saved as text for ingestion.

To extend with NAEYC position statements or state licensing rules, drop your
own PDFs / markdown / text files into data/raw/ and re-run `python -m src.ingest`.

Run: python -m scripts.download_corpus
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx
from tqdm import tqdm

DATA_RAW = Path("data/raw")

# CDC Milestone Tracker PDFs (English). U.S. gov public domain.
CDC_CORPUS = [
    ("cdc_milestones_2_months.pdf",   "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/2mo_eng_504.pdf"),
    ("cdc_milestones_4_months.pdf",   "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/4mo_eng_504.pdf"),
    ("cdc_milestones_6_months.pdf",   "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/6mo_eng_504.pdf"),
    ("cdc_milestones_9_months.pdf",   "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/9mo_eng_504.pdf"),
    ("cdc_milestones_12_months.pdf",  "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/12mo_eng_504.pdf"),
    ("cdc_milestones_15_months.pdf",  "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/15mo_eng_504.pdf"),
    ("cdc_milestones_18_months.pdf",  "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/18mo_eng_504.pdf"),
    ("cdc_milestones_2_years.pdf",    "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/2yr_eng_504.pdf"),
    ("cdc_milestones_3_years.pdf",    "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/3yr_eng_504.pdf"),
    ("cdc_milestones_4_years.pdf",    "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/4yr_eng_504.pdf"),
    ("cdc_milestones_5_years.pdf",    "https://www.cdc.gov/ncbddd/actearly/pdf/checklists/5yr_eng_504.pdf"),
]

# 45 CFR Part 1302 (Head Start Program Performance Standards) — fetched from eCFR.
# We pull per-subpart HTML pages and strip to text. Public domain (federal regs).
HEAD_START_SUBPARTS = [
    ("A", "Eligibility-Recruitment-Selection-Enrollment-Attendance"),
    ("B", "Program-Structure"),
    ("C", "Education-and-Child-Development-Program-Services"),
    ("D", "Health-Program-Services"),
    ("E", "Family-and-Community-Engagement-Program-Services"),
    ("F", "Additional-Services-for-Children-with-Disabilities"),
    ("G", "Transition-Services"),
    ("H", "Services-to-Enrolled-Pregnant-Women"),
    ("I", "Human-Resources-Management"),
    ("J", "Program-Management-and-Quality-Improvement"),
]
HEAD_START_BASE = (
    "https://www.ecfr.gov/api/renderer/v1/content/enhanced/current/title-45"
    "?chapter=XIII&subchapter=B&part=1302&subpart={letter}"
)


def _strip_html(text: str) -> str:
    """Crude HTML → text. Good enough for eCFR's clean markup."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_cdc(client: httpx.Client) -> tuple[int, list[tuple[str, str]]]:
    failed: list[tuple[str, str]] = []
    ok = 0
    for fname, url in tqdm(CDC_CORPUS, desc="CDC milestones"):
        dst = DATA_RAW / fname
        if dst.exists() and dst.stat().st_size > 0:
            ok += 1
            continue
        try:
            r = client.get(url)
            if r.status_code != 200:
                failed.append((fname, f"HTTP {r.status_code}"))
                continue
            dst.write_bytes(r.content)
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed.append((fname, str(e)))
    return ok, failed


def fetch_head_start(client: httpx.Client) -> tuple[int, list[tuple[str, str]]]:
    failed: list[tuple[str, str]] = []
    ok = 0
    for letter, slug in tqdm(HEAD_START_SUBPARTS, desc="Head Start (45 CFR 1302)"):
        fname = f"head_start_1302_subpart_{letter}_{slug}.txt"
        dst = DATA_RAW / fname
        if dst.exists() and dst.stat().st_size > 0:
            ok += 1
            continue
        try:
            r = client.get(HEAD_START_BASE.format(letter=letter))
            if r.status_code != 200:
                failed.append((fname, f"HTTP {r.status_code}"))
                continue
            body = _strip_html(r.text)
            if len(body) < 500:
                failed.append((fname, f"body too short ({len(body)} chars)"))
                continue
            header = f"45 CFR Part 1302 — Head Start Performance Standards — Subpart {letter}: {slug.replace('-', ' ')}\n\n"
            dst.write_text(header + body, encoding="utf-8")
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed.append((fname, str(e)))
    return ok, failed


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print(f"Downloading public-domain corpora into {DATA_RAW}/ ...\n")

    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "ComplianceIQ/0.1"}) as client:
        cdc_ok, cdc_failed = fetch_cdc(client)
        head_ok, head_failed = fetch_head_start(client)

    print()
    print(f"  CDC milestones:       {cdc_ok}/{len(CDC_CORPUS)} downloaded")
    print(f"  Head Start subparts:  {head_ok}/{len(HEAD_START_SUBPARTS)} downloaded")

    failed = cdc_failed + head_failed
    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for fname, reason in failed:
            print(f"  - {fname}: {reason}")
        print(
            "\nFailures are non-fatal. Continue with what was fetched; "
            "or drop any .txt/.md/.pdf into data/raw/ yourself and re-run `python -m src.ingest`."
        )

    total = cdc_ok + head_ok
    if total == 0:
        raise SystemExit(
            "No documents downloaded. Check network connectivity or supply your "
            "own corpus by dropping files into data/raw/ manually."
        )
    print(f"\n✓ {total} documents available in {DATA_RAW}/")


if __name__ == "__main__":
    main()
