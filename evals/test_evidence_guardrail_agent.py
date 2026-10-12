"""
Seam under test: review_evidence_citations(records) — the citation-check
critic that runs before any finding reaches the final report.

Rule: a red-flag claim someone can't click through and verify shouldn't
reach the report. Every other tag (clean, confirmed-by-absence, unresolved,
vendor-declared) doesn't assert a confirmed wrongdoing, so it isn't held to
the citation bar.
"""
from datetime import date

from agents.evidence_guardrail import review_evidence_citations
from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)


def _record(tag: FindingTag, citation_url: str | None) -> EvidenceRecord:
    return EvidenceRecord(
        vendor_id="vendor-b-patel-and-sons",
        category=FindingCategory.GLOBAL_COMPLIANCE,
        source_name="OpenSanctions",
        source_reference="us_ofac_sdn",
        summary="Name match scored 1.0 against OFAC SDN list",
        tag=tag,
        confidence_tier=ConfidenceTier.TIER_2,
        as_of_date=date(2026, 9, 27),
        check_status=CheckStatus.SUCCESS,
        citation_url=citation_url,
    )


def test_a_red_flag_with_no_citation_is_rejected():
    unsourced = _record(FindingTag.RESOLVED_RED_FLAG, citation_url=None)

    accepted, rejected = review_evidence_citations([unsourced])

    assert accepted == []
    assert rejected == [unsourced]


def test_a_red_flag_with_a_citation_is_accepted():
    sourced = _record(
        FindingTag.RESOLVED_RED_FLAG,
        citation_url="https://sanctionssearch.ofac.treas.gov/Details.aspx?id=35096",
    )

    accepted, rejected = review_evidence_citations([sourced])

    assert accepted == [sourced]
    assert rejected == []


def test_a_clean_finding_with_no_citation_is_still_accepted():
    clean = _record(FindingTag.RESOLVED_CLEAN, citation_url=None)

    accepted, rejected = review_evidence_citations([clean])

    assert accepted == [clean]
    assert rejected == []
