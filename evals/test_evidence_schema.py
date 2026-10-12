"""
Seam under test: constructing an EvidenceRecord through its public constructor.

Literals below come from real API responses we captured live during setup —
see evals/fixtures/opensanctions_putin_match.json and
evals/fixtures/indiankanoon_cheque_bounce_search.json — not invented numbers.
"""
from datetime import date

import pytest
from pydantic import ValidationError

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)


def test_records_a_confirmed_sanctions_hit_from_a_real_opensanctions_match():
    # Real values from evals/fixtures/opensanctions_putin_match.json
    record = EvidenceRecord(
        vendor_id="vendor-b-patel-and-sons",
        category=FindingCategory.GLOBAL_COMPLIANCE,
        source_name="OpenSanctions",
        source_reference="us_ofac_sdn",  # the cited dataset, not just "OpenSanctions"
        summary="Name match 'Vladimir Putin' scored 1.0 against OFAC SDN list",
        tag=FindingTag.RESOLVED_RED_FLAG,
        confidence_tier=ConfidenceTier.TIER_2,
        as_of_date=date(2026, 9, 27),  # last_seen date from the real response
        check_status=CheckStatus.SUCCESS,
        citation_url="https://sanctionssearch.ofac.treas.gov/Details.aspx?id=35096",
    )

    assert record.tag == FindingTag.RESOLVED_RED_FLAG
    assert record.confidence_tier == ConfidenceTier.TIER_2
    assert record.citation_url is not None


def test_a_technical_failure_can_never_be_recorded_as_resolved_clean():
    # Spec line 314: "A failed check is never silently recorded as
    # resolved-clean — the schema has no path from a technical failure
    # directly to a clean tag."
    with pytest.raises(ValidationError):
        EvidenceRecord(
            vendor_id="vendor-a-suresh-enterprises",
            category=FindingCategory.LITIGATION,
            source_name="Indian Kanoon",
            source_reference="tid:87659573",
            summary="Search timed out after 3 retries",
            tag=FindingTag.RESOLVED_CLEAN,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date(2026, 9, 29),
            check_status=CheckStatus.TECHNICAL_FAILURE,
            citation_url=None,
        )
