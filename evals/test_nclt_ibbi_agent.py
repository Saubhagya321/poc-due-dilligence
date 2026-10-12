"""
Seam under test: agents.nclt_ibbi.screen_nclt_ibbi(vendor, dataset).

NCLT jurisdiction only covers Companies Act entities + LLPs, so the agent
should produce no record for a sole prop / HUF / partnership — matching
how the orchestrator's _applicability() gates CanonicalCheck.NCLT.
"""
from decimal import Decimal

from agents.nclt_ibbi import screen_nclt_ibbi
from schemas.evidence import FindingTag
from schemas.vendor import EntityType, VendorIntake
from tools.ibbi import CirpDataset, CirpRecord


def _vendor(**overrides):
    base = dict(
        vendor_id="v1",
        name="Acme Private Limited",
        pan="AAACA1234C",
        entity_type=EntityType.PRIVATE_LIMITED,
        contract_value=Decimal("10000000"),
        has_physical_premises=True,
    )
    base.update(overrides)
    return VendorIntake(**base)


def _dataset(*records: CirpRecord) -> CirpDataset:
    return CirpDataset.from_records(records)


def _cirp(cin=None, debtor="Something Private Limited") -> CirpRecord:
    return CirpRecord(
        announcement_type="Public Announcement of Corporate Insolvency Resolution Process",
        date_of_announcement="08-10-2026",
        last_date_of_submission="22-10-2026",
        corporate_debtor=debtor,
        cin=cin,
        applicant="Yes Bank",
        insolvency_professional="Nilesh Kothari",
    )


def test_cin_hit_becomes_red_flag():
    dataset = _dataset(_cirp(cin="U72900KA2015PTC082988", debtor="Acme Private Limited"))

    records = screen_nclt_ibbi(_vendor(cin="U72900KA2015PTC082988"), dataset)

    assert len(records) == 1
    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG
    assert "insolvency" in records[0].summary.lower()


def test_no_match_becomes_clean():
    dataset = _dataset(_cirp(cin="U99999XX9999XXX999999", debtor="Other Private Limited"))

    records = screen_nclt_ibbi(_vendor(cin="U72900KA2015PTC082988"), dataset)

    assert len(records) == 1
    assert records[0].tag == FindingTag.RESOLVED_CLEAN


def test_name_hit_without_cin_becomes_red():
    # Vendor has no CIN but shares distinctive tokens with a CIRP debtor —
    # still a red flag, we just can't be as confident as a CIN match.
    dataset = _dataset(_cirp(cin=None, debtor="ACME PRIVATE LIMITED"))

    records = screen_nclt_ibbi(_vendor(cin=None), dataset)

    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG


def test_not_applicable_for_sole_proprietorship():
    dataset = _dataset(_cirp(cin="U72900KA2015PTC082988", debtor="Acme Private Limited"))

    records = screen_nclt_ibbi(
        _vendor(entity_type=EntityType.SOLE_PROPRIETORSHIP, pan="AMMPK4657M", cin=None),
        dataset,
    )

    assert records == []


def test_empty_dataset_still_produces_clean_record():
    # If the weekly scrape hasn't run yet the dataset is empty — the agent
    # still has to emit SOMETHING so the NCLT tile doesn't stay grey. A
    # clean-by-absence record is the right answer: we checked and found
    # nothing, which is true (the empty set contains no match).
    dataset = _dataset()

    records = screen_nclt_ibbi(_vendor(cin="U72900KA2015PTC082988"), dataset)

    assert records[0].tag == FindingTag.RESOLVED_CLEAN
