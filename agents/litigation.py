from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
    SupportingCitation,
)
from schemas.vendor import VendorIntake
from tools.indian_kanoon import ecourts_case_search

PATTERN_THRESHOLD = 3


def screen_litigation(vendor: VendorIntake, indian_kanoon_api_key: str) -> list[EvidenceRecord]:
    """
    Runs the eCourts cheque-bounce search and classifies what comes back.

    3+ cases naming this vendor is a pattern of cheque dishonour — a
    repeated payment-default signal worth prioritising. 1-2 is a milder,
    possibly one-off dispute. Neither can be confirmed as genuinely this
    vendor from a case title alone (no PAN in judgments), so both stay
    unresolved and route to a human; only the wording says how urgent it
    is. No matching cases is confirmed-by-absence: we looked in the
    judicial record and found nothing.
    """
    docs = ecourts_case_search(name=vendor.name, api_key=indian_kanoon_api_key)

    if not docs:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.LITIGATION,
                source_name="Indian Kanoon",
                source_reference="no-cases-found",
                summary=f"No litigation hits (NI Act 138 / fraud / money laundering / NCLT) found for '{vendor.name}'.",
                tag=FindingTag.CONFIRMED_BY_ABSENCE,
                confidence_tier=ConfidenceTier.TIER_2,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
            )
        ]

    top = docs[0]
    citation_url = f"https://indiankanoon.org/doc/{top['tid']}/"
    supporting_citations = [
        SupportingCitation(
            title=doc.get("title", "untitled"),
            url=f"https://indiankanoon.org/doc/{doc['tid']}/",
            source=doc.get("docsource", "unknown court"),
        )
        for doc in docs
    ]

    if len(docs) >= PATTERN_THRESHOLD:
        summary = (
            f"Pattern flag: {len(docs)} litigation hits (NI Act 138 / fraud / money laundering / NCLT) found naming "
            f"'{vendor.name}', top match: '{top['title']}' ({top.get('docsource', 'unknown court')}) "
            "— identity not confirmed, needs human cross-check against vendor PAN."
        )
    else:
        summary = (
            f"Isolated case: {len(docs)} cheque-bounce / NI Act 138 case found naming "
            f"'{vendor.name}': '{top['title']}' ({top.get('docsource', 'unknown court')}) "
            "— identity not confirmed, needs human cross-check against vendor PAN."
        )

    return [
        EvidenceRecord(
            vendor_id=vendor.vendor_id,
            category=FindingCategory.LITIGATION,
            source_name="Indian Kanoon",
            source_reference=str(top["tid"]),
            summary=summary,
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url=citation_url,
            supporting_citations=supporting_citations,
        )
    ]
