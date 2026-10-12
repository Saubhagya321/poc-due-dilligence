"""
GST tile — automated via eKYC Now.

Two-step flow:
  1. /kyb/pan-to-gstin  -> list of GSTINs this PAN is registered under
                           (one entry per state)
  2. /kyb/gstin          -> for each GSTIN, fetch status + legal name +
                           principal place (first N states; cap to keep
                           credit cost sane)

Classification over the whole set:
  - zero GSTINs returned          -> UNRESOLVED (vendor may not be
                                     GST-registered, or PAN wrong — the
                                     analyst decides)
  - all GSTINs Active             -> RESOLVED_CLEAN
  - any GSTIN Cancelled/Suspended -> RESOLVED_RED_FLAG (lost input credit
                                     risk on that state's invoices)
  - mixed / unknown statuses      -> UNRESOLVED

Not applicable for FOREIGN_ENTITY (no Indian PAN).
"""
from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
    SupportingCitation,
)
from schemas.vendor import EntityType, VendorIntake
from tools.ekyc import EkycError, EkycInvalidInput, fetch_gstin_with_pan, verify_gstin

SOURCE_NAME = "eKYC Now (GST)"

_RED_STATUSES = {"CANCELLED", "SUSPENDED", "INACTIVE"}
_MAX_GSTINS_TO_VERIFY = 5  # cap per-vendor credit cost


def _tech_fail(vendor_id: str, reason: str) -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            vendor_id=vendor_id,
            category=FindingCategory.INDIA_REGULATORY,
            source_name=SOURCE_NAME,
            source_reference="technical-failure",
            summary=f"GST lookup failed: {reason}. Retry needed.",
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_1,
            as_of_date=date.today(),
            check_status=CheckStatus.TECHNICAL_FAILURE,
        )
    ]


def screen_gst(vendor: VendorIntake, api_key: str, customer_id: str) -> list[EvidenceRecord]:
    if vendor.entity_type == EntityType.FOREIGN_ENTITY:
        return []
    if not vendor.pan:
        return []
    if not api_key or not customer_id:
        return []

    try:
        pan_payload = fetch_gstin_with_pan(vendor.pan, api_key, customer_id)
    except EkycInvalidInput as exc:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=vendor.pan,
                summary=f"PAN -> GST lookup rejected PAN '{vendor.pan}': {exc}.",
                tag=FindingTag.UNRESOLVED,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.AMBIGUOUS_MATCH,
            )
        ]
    except EkycError as exc:
        return _tech_fail(vendor.vendor_id, str(exc))

    gstin_list = pan_payload.get("gstin_list") or []
    citation_url = "https://services.gst.gov.in/services/searchtp"

    if not gstin_list:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=vendor.pan,
                summary=(
                    f"No GSTINs found for PAN '{vendor.pan}'. Vendor may not be "
                    "GST-registered — analyst to confirm whether this is "
                    "expected for the vendor's entity type and turnover."
                ),
                tag=FindingTag.UNRESOLVED,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.AMBIGUOUS_MATCH,
                citation_url=citation_url,
            )
        ]

    # Verify each GSTIN (capped). Any technical failure here is logged but
    # we don't abort — a partial list is still useful.
    verified: list[dict] = []
    for entry in gstin_list[:_MAX_GSTINS_TO_VERIFY]:
        gstin = entry.get("gstin")
        if not gstin:
            continue
        try:
            payload = verify_gstin(gstin, api_key, customer_id)
            verified.append(payload)
        except (EkycError, EkycInvalidInput) as exc:
            verified.append({"GSTIN": gstin, "gst_in_status": "LOOKUP_FAILED", "message": str(exc)})

    red_hits = [v for v in verified if str(v.get("gst_in_status", "")).upper() in _RED_STATUSES]
    active_hits = [v for v in verified if str(v.get("gst_in_status", "")).upper() == "ACTIVE"]

    supporting = [
        SupportingCitation(
            title=(
                f"{v.get('GSTIN', '?')} — {v.get('legal_name_of_business', vendor.name)} — "
                f"{v.get('gst_in_status', 'status unknown')}"
            ),
            url=f"https://services.gst.gov.in/services/searchtpbypan",
            source="eKYC Now",
        )
        for v in verified
    ]

    if red_hits:
        worst = red_hits[0]
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=worst.get("GSTIN", vendor.pan),
                summary=(
                    f"{len(red_hits)} of {len(verified)} GSTIN(s) are "
                    f"Cancelled / Suspended, e.g. {worst.get('GSTIN', '?')} "
                    f"({worst.get('legal_name_of_business', vendor.name)}, "
                    f"status: {worst.get('gst_in_status', '?')})."
                ),
                tag=FindingTag.RESOLVED_RED_FLAG,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url=citation_url,
                supporting_citations=supporting,
            )
        ]

    if active_hits and len(active_hits) == len(verified):
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=vendor.pan,
                summary=(
                    f"All {len(verified)} GSTIN(s) under PAN '{vendor.pan}' are "
                    "Active and in good standing."
                ),
                tag=FindingTag.RESOLVED_CLEAN,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url=citation_url,
                supporting_citations=supporting,
            )
        ]

    # Mixed, unknown, or lookup failures — amber, needs human.
    return [
        EvidenceRecord(
            vendor_id=vendor.vendor_id,
            category=FindingCategory.INDIA_REGULATORY,
            source_name=SOURCE_NAME,
            source_reference=vendor.pan,
            summary=(
                f"{len(verified)} GSTIN(s) found under PAN '{vendor.pan}' with "
                "mixed or unresolved statuses — analyst to review each."
            ),
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_1,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url=citation_url,
            supporting_citations=supporting,
        )
    ]
