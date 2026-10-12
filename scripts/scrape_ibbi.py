"""
Weekly scrape of the IBBI public-announcement CIRP dataset.

Run manually or via cron:
    python scripts/scrape_ibbi.py

Writes data/ibbi_cirp.tsv (overwriting the previous snapshot). The NCLT
agent loads this file at process start.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ibbi import DEFAULT_DATASET_PATH, fetch_ibbi_export, parse_ibbi_tsv


def main() -> int:
    print(f"Downloading IBBI CIRP export from live endpoint...")
    raw = fetch_ibbi_export()
    print(f"  downloaded {len(raw):,} bytes")

    records = parse_ibbi_tsv(raw)
    with_cin = sum(1 for r in records if r.cin)
    print(f"  parsed {len(records):,} records ({with_cin:,} with CIN)")

    DEFAULT_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_DATASET_PATH.write_bytes(raw)
    print(f"  wrote {DEFAULT_DATASET_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
