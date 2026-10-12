"""
Seam under test: tools.ibbi.parse_ibbi_tsv + CirpDataset lookups.

IBBI's /public-announcement?export_excel=export_excel endpoint serves a
tab-separated file (mislabeled application/ms-excel). We parse it offline
once per week and query the resulting dataset per-vendor without any
network call at screening time.
"""
from tools.ibbi import CirpDataset, parse_ibbi_tsv

_HEADER = (
    "Announcement Type\t Date of Announcement\t Last date of Submission\t "
    "Name of Corporate Debtor\t CIN No.\t Name of Applicant\t "
    "Name of Insolvency Professional\t Address of Insolvency Professional\t Remarks\n"
)
_ROW_WITH_CIN = (
    "Public Announcement of Corporate Insolvency Resolution Process\t 08-10-2026\t "
    "22-10-2026\t SRIRAM INFRAPROJECTS &amp; VENTURES PRIVATE LIMITED\t "
    "U70100KA2011PTC060474\t YES BANK LIMITED\t Nilesh Kothari\t Mumbai\t \n"
)
_ROW_WITHOUT_CIN = (
    "Public Announcement of Voluntary Liquidation Process\t 01-01-2024\t "
    "01-02-2024\t SOME LLP THING\t \t Applicant X\t IP Y\t Delhi\t \n"
)


def test_parse_ibbi_tsv_extracts_rows():
    raw = (_HEADER + _ROW_WITH_CIN + _ROW_WITHOUT_CIN).encode("utf-8")

    records = parse_ibbi_tsv(raw)

    assert len(records) == 2
    assert records[0].cin == "U70100KA2011PTC060474"
    # HTML entities should be decoded (&amp; -> &)
    assert "&" in records[0].corporate_debtor
    assert "SRIRAM" in records[0].corporate_debtor
    assert records[1].cin is None  # blank CIN cell -> None, not ""


def test_dataset_find_by_cin_is_exact_and_case_insensitive():
    raw = (_HEADER + _ROW_WITH_CIN).encode("utf-8")
    dataset = CirpDataset.from_bytes(raw)

    hit = dataset.find_by_cin("u70100ka2011ptc060474")
    assert hit is not None
    assert hit.corporate_debtor.startswith("SRIRAM")

    miss = dataset.find_by_cin("U99999XX9999XXX999999")
    assert miss is None


def test_dataset_find_by_name_requires_distinctive_token_overlap():
    raw = (_HEADER + _ROW_WITH_CIN).encode("utf-8")
    dataset = CirpDataset.from_bytes(raw)

    # Legitimate token overlap on "SRIRAM" — a real hit.
    hits = dataset.find_by_name("Sriram Infraprojects Private Limited")
    assert len(hits) == 1

    # Only stopword overlap ("private limited") must not match — otherwise
    # every private limited vendor in India would false-positive against
    # every private limited CIRP filing.
    hits = dataset.find_by_name("Completely Different Private Limited")
    assert hits == []
