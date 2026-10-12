"""
MCA tile — automated via eKYC Now's /kyb/cin endpoint.

Routing:
  - Only applicable to entity_type in {LLP, OPC, PRIVATE_LIMITED, PUBLIC_LIMITED}
    (same rule the orchestrator uses to mark the MCA tile applicable).
  - Only fires if vendor.cin is supplied at intake. Vendors without a declared
    CIN keep the MCA tile grey — the analyst can still use web research /
    document upload like before.

Classification:
  - cin_status == "ACTIVE"              -> RESOLVED_CLEAN
  - cin_status in {STRIKE OFF, UNDER LIQUIDATION, DISSOLVED, AMALGAMATED,
    "UNDER PROCESS OF STRIKING OFF", ...}  -> RESOLVED_RED_FLAG (contracts
    with a struck-off company are legally void)
  - cin_status == "DORMANT" / anything else known   -> UNRESOLVED (amber,
    needs analyst to check what the dormancy means for this contract)
  - EkycInvalidInput at intake-time   -> never reach the pipeline (format
    error surfaces at vendor save)
  - EkycError (network / 5xx / unexpected envelope)  -> UNRESOLVED with
    CheckStatus.TECHNICAL_FAILURE, so the UI shows "temporarily unavailable"
    rather than crashing the whole screening.
"""
from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)
from schemas.vendor import EntityType, VendorIntake
from tools.ekyc import EkycError, EkycInvalidInput, verify_cin

SOURCE_NAME = "eKYC Now (MCA/CIN)"

_RED_STATUSES = {
    "STRIKE OFF",
    "STRUCK OFF",
    "UNDER LIQUIDATION",
    "UNDER PROCESS OF STRIKING OFF",
    "DISSOLVED",
    "AMALGAMATED",
    "CONVERTED AND DISSOLVED",
}

_APPLICABLE_TYPES = {
    EntityType.LLP,
    EntityType.OPC,
    EntityType.PRIVATE_LIMITED,
    EntityType.PUBLIC_LIMITED,
}


def screen_mca(vendor: VendorIntake, api_key: str, customer_id: str) -> list[EvidenceRecord]:
    if vendor.entity_type not in _APPLICABLE_TYPES:
        return []
    if not vendor.cin:
        # Analyst didn't supply a CIN — leave the tile grey; the manual
        # path (web research / doc upload) still works.
        return []
    if not api_key or not customer_id:
        return []

    try:
        payload = verify_cin(vendor.cin, api_key, customer_id)
    except EkycInvalidInput as exc:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=vendor.cin,
                summary=f"CIN '{vendor.cin}' failed MCA validation: {exc}.",
                tag=FindingTag.UNRESOLVED,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.AMBIGUOUS_MATCH,
            )
        ]
    except EkycError as exc:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference="technical-failure",
                summary=f"MCA/CIN lookup for '{vendor.cin}' failed: {exc}. Retry needed.",
                tag=FindingTag.UNRESOLVED,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.TECHNICAL_FAILURE,
            )
        ]

    cin_status = str(payload.get("cin_status", "")).strip().upper()
    company_name = payload.get("company_name") or vendor.name
    incorporation_date = payload.get("incorporation_date") or "unknown"
    citation_url = f"https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do"

    if cin_status in _RED_STATUSES:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=payload.get("cin", vendor.cin),
                summary=(
                    f"MCA shows '{company_name}' as '{cin_status}' — contracts with "
                    f"a struck-off / dissolved / liquidated company are legally void."
                ),
                tag=FindingTag.RESOLVED_RED_FLAG,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url=citation_url,
            )
        ]

    if cin_status == "ACTIVE":
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=payload.get("cin", vendor.cin),
                summary=(
                    f"MCA confirms '{company_name}' is ACTIVE (incorporated "
                    f"{incorporation_date})."
                ),
                tag=FindingTag.RESOLVED_CLEAN,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url=citation_url,
            )
        ]

    # Any other status (DORMANT, UNKNOWN, blank) — analyst must verify.
    return [
        EvidenceRecord(
            vendor_id=vendor.vendor_id,
            category=FindingCategory.INDIA_REGULATORY,
            source_name=SOURCE_NAME,
            source_reference=payload.get("cin", vendor.cin),
            summary=(
                f"MCA returned non-standard status '{cin_status}' for "
                f"'{company_name}' — needs analyst review."
            ),
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_1,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url=citation_url,
        )
    ]
