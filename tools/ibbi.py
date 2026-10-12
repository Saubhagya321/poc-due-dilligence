"""
IBBI public-announcement dataset — local scrape of corporate insolvency
filings used to automate the NCLT tile without the ~Rs.99/vendor cost of
eCourts India LegalCheck.

Source: https://ibbi.gov.in/public-announcement?export_excel=export_excel
Despite the content-type (application/ms-excel) and .xlsx extension the
endpoint actually returns a UTF-8 TSV. ~15k rows, ~97% carry a CIN.

Freshness model: scraped weekly into data/ibbi_cirp.tsv, loaded once per
process. Lookups at screening time are pure dict/set operations — no
network call per vendor.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import httpx

EXPORT_URL = "https://ibbi.gov.in/public-announcement?export_excel=export_excel"
DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "ibbi_cirp.tsv"

# Tokens that carry no identity signal — a vendor and a CIRP filing both
# being "private limited" means nothing. Everything in this set is stripped
# before name-based matching so we don't fire false positives on common
# corporate suffixes.
_STOPWORDS = {
    "private", "pvt", "limited", "ltd", "llp", "india",
    "and", "the", "of", "co", "company", "corp", "corporation",
    "incorporated", "inc", "enterprises", "enterprise", "services",
    "solutions", "industries", "group",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class CirpRecord:
    announcement_type: str
    date_of_announcement: str
    last_date_of_submission: str
    corporate_debtor: str
    cin: Optional[str]
    applicant: str
    insolvency_professional: str


def _distinctive_tokens(name: str) -> set[str]:
    tokens = _TOKEN_RE.findall(name.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def parse_ibbi_tsv(raw: bytes) -> list[CirpRecord]:
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return []

    out: list[CirpRecord] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = [html.unescape(c.strip()) for c in line.split("\t")]
        if len(cells) < 7:
            continue
        cin_raw = cells[4].strip()
        out.append(
            CirpRecord(
                announcement_type=cells[0],
                date_of_announcement=cells[1],
                last_date_of_submission=cells[2],
                corporate_debtor=cells[3],
                cin=cin_raw.upper() if cin_raw and cin_raw.upper() != "NA" else None,
                applicant=cells[5],
                insolvency_professional=cells[6],
            )
        )
    return out


@dataclass
class CirpDataset:
    records: list[CirpRecord]
    _by_cin: dict[str, CirpRecord]
    _by_token: dict[str, list[CirpRecord]]

    @classmethod
    def from_records(cls, records: Iterable[CirpRecord]) -> "CirpDataset":
        records = list(records)
        by_cin: dict[str, CirpRecord] = {}
        by_token: dict[str, list[CirpRecord]] = {}
        for r in records:
            if r.cin:
                by_cin[r.cin.upper()] = r
            for tok in _distinctive_tokens(r.corporate_debtor):
                by_token.setdefault(tok, []).append(r)
        return cls(records=records, _by_cin=by_cin, _by_token=by_token)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CirpDataset":
        return cls.from_records(parse_ibbi_tsv(raw))

    @classmethod
    def from_path(cls, path: Path = DEFAULT_DATASET_PATH) -> "CirpDataset":
        if not path.exists():
            return cls.from_records([])
        return cls.from_bytes(path.read_bytes())

    def find_by_cin(self, cin: Optional[str]) -> Optional[CirpRecord]:
        if not cin:
            return None
        return self._by_cin.get(cin.strip().upper())

    def find_by_name(self, name: str) -> list[CirpRecord]:
        tokens = _distinctive_tokens(name)
        if not tokens:
            return []
        # A vendor name must share ALL its distinctive tokens with the
        # debtor name — a single stopword-filtered overlap on a common
        # word ("global", "tech") would fire on every CIRP in the sector.
        candidates: list[CirpRecord] = []
        for tok in tokens:
            for r in self._by_token.get(tok, []):
                debtor_tokens = _distinctive_tokens(r.corporate_debtor)
                if tokens.issubset(debtor_tokens):
                    if r not in candidates:
                        candidates.append(r)
        return candidates


def fetch_ibbi_export(timeout: float = 120.0) -> bytes:
    """Download the current full IBBI CIRP TSV. Called by the weekly scraper."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(EXPORT_URL)
        resp.raise_for_status()
        return resp.content
