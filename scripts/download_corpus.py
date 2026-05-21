"""Download public-domain early-childhood-education documents into data/raw/.

Uses CDC 'Learn the Signs. Act Early.' developmental-milestone resources.
These are U.S. government works, public domain, freely redistributable.

Run: python -m scripts.download_corpus
"""
from __future__ import annotations

from pathlib import Path

import httpx
from tqdm import tqdm

DATA_RAW = Path("data/raw")

# Curated set of public-domain CDC developmental-milestone PDFs.
# These are checked URLs as of 2026-05-21. If any 404, the script reports and continues.
CORPUS = [
    # CDC Milestone Tracker PDFs (English)
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


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(CORPUS)} files into {DATA_RAW}/ ...")
    failed: list[tuple[str, str]] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for fname, url in tqdm(CORPUS, desc="downloading"):
            dst = DATA_RAW / fname
            if dst.exists() and dst.stat().st_size > 0:
                continue
            try:
                r = client.get(url)
                if r.status_code != 200:
                    failed.append((fname, f"HTTP {r.status_code}"))
                    continue
                dst.write_bytes(r.content)
            except Exception as e:  # noqa: BLE001
                failed.append((fname, str(e)))

    ok = sum(1 for f, _ in CORPUS if (DATA_RAW / f).exists())
    print(f"\nDownloaded: {ok}/{len(CORPUS)} files into {DATA_RAW}/")
    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for fname, reason in failed:
            print(f"  - {fname}: {reason}")
        print(
            "\nIf many URLs 404, the CDC may have reorganized their site. "
            "Drop any .txt/.md/.pdf into data/raw/ yourself and re-run ingest."
        )


if __name__ == "__main__":
    main()
