"""
Seam under test: record_manual_finding(vendor_id, check, tag, summary,
citation_url) — the entry point an analyst's checklist submission goes
through to become a citable EvidenceRecord, same shape as any automated
tool's finding.

Restricted to checks listed in tools/manual_checklist.py's INSTRUCTIONS —
those are exactly the checks with no automated path in this PoC. Anything
else already has a live tool that should be the source of truth, so a
manual override there is rejected rather than silently accepted.
"""
import pytest

from schemas.evidence import CheckStatus, ConfidenceTier, FindingCategory, FindingTag
from schemas.report import CanonicalCheck
from agents.manual_findings import record_manual_finding


def test_active_gst_registration_is_resolved_clean():
    record = record_manual_finding(
        vendor_id="vendor-acme",
        check=CanonicalCheck.GST,
        tag=FindingTag.RESOLVED_CLEAN,
        summary="GSTIN 29AACCA1234B1Z0 is Active with clean return filing history.",
    )

    assert record.tag == FindingTag.RESOLVED_CLEAN
    assert record.check_status == CheckStatus.SUCCESS
    assert record.category == FindingCategory.INDIA_REGULATORY
    assert record.confidence_tier == ConfidenceTier.TIER_1
    assert record.source_name == "Analyst manual entry"
    assert record.source_reference == CanonicalCheck.GST.value


def test_sfio_prosecution_found_is_resolved_red_flag_with_citation():
    record = record_manual_finding(
        vendor_id="vendor-defunct",
        check=CanonicalCheck.SFIO,
        tag=FindingTag.RESOLVED_RED_FLAG,
        summary="SFIO inspection report dated 2022 names this company.",
        citation_url="https://www.mca.gov.in/some-report.pdf",
    )

    assert record.tag == FindingTag.RESOLVED_RED_FLAG
    assert record.check_status == CheckStatus.SUCCESS
    assert record.citation_url == "https://www.mca.gov.in/some-report.pdf"


def test_analyst_could_not_confirm_is_unresolved():
    record = record_manual_finding(
        vendor_id="vendor-acme",
        check=CanonicalCheck.EPFO,
        tag=FindingTag.UNRESOLVED,
        summary="EPFO portal did not return a matching establishment for this PAN.",
    )

    assert record.tag == FindingTag.UNRESOLVED
    assert record.check_status == CheckStatus.AMBIGUOUS_MATCH


def test_check_with_an_automated_path_is_rejected():
    with pytest.raises(ValueError, match="pan_verification"):
        record_manual_finding(
            vendor_id="vendor-acme",
            check=CanonicalCheck.PAN_VERIFICATION,
            tag=FindingTag.RESOLVED_CLEAN,
            summary="Looks fine to me.",
        )


def test_vendor_declared_tag_is_rejected():
    with pytest.raises(ValueError, match="vendor-declared"):
        record_manual_finding(
            vendor_id="vendor-acme",
            check=CanonicalCheck.GST,
            tag=FindingTag.VENDOR_DECLARED,
            summary="Vendor says it's fine.",
        )
