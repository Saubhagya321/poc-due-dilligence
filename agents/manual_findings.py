from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
    SupportingCitation,
)
from schemas.report import CanonicalCheck
from tools.manual_checklist import INSTRUCTIONS

SOURCE_NAME = "Analyst manual entry"

_STATUS_BY_TAG = {
    FindingTag.RESOLVED_CLEAN: CheckStatus.SUCCESS,
    FindingTag.RESOLVED_RED_FLAG: CheckStatus.SUCCESS,
    FindingTag.CONFIRMED_BY_ABSENCE: CheckStatus.SUCCESS,
    FindingTag.UNRESOLVED: CheckStatus.AMBIGUOUS_MATCH,
}


def record_manual_finding(
    vendor_id: str,
    check: CanonicalCheck,
    tag: FindingTag,
    summary: str,
    citation_url: str | None = None,
    supporting_citations: list[SupportingCitation] | None = None,
) -> EvidenceRecord:
    """
    Converts an analyst's manual-checklist finding into a citable
    EvidenceRecord, the same shape the automated tools produce.

    Restricted to checks listed in tools/manual_checklist.py's
    INSTRUCTIONS — those are precisely the checks with no automated path
    in this PoC. A check that already has a live tool (e.g. PAN, sanctions)
    should come from that tool, not a manual override, so it's rejected
    here. VENDOR_DECLARED is likewise rejected: that tag means "the vendor
    told us", a different provenance than "an analyst looked it up".
    """
    if check not in INSTRUCTIONS:
        raise ValueError(
            f"'{check.value}' has an automated check — analysts can't submit a manual finding for it."
        )
    if tag not in _STATUS_BY_TAG:
        raise ValueError(f"Analyst findings can't be tagged '{tag.value}'.")

    return EvidenceRecord(
        vendor_id=vendor_id,
        category=FindingCategory.INDIA_REGULATORY,
        source_name=SOURCE_NAME,
        source_reference=check.value,
        summary=summary,
        tag=tag,
        confidence_tier=ConfidenceTier.TIER_1,
        as_of_date=date.today(),
        check_status=_STATUS_BY_TAG[tag],
        citation_url=citation_url,
        supporting_citations=supporting_citations or [],
    )
