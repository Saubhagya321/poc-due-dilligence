"""
MSME/Udyam tile — automated via eKYC Now's /kyb/udyam endpoint.

Only fires if vendor.udyam_number is supplied at intake. Vendors who aren't
MSME-registered or don't declare their Udyam number keep the tile grey —
the analyst can still submit a manual finding ("not applicable: large
enterprise above MSME threshold") or upload the Udyam certificate PDF.

Classification:
  - status == "SUCCESS" + enterprise_type in {Micro, Small, Medium}  -> CLEAN
  - Udyam not found / cancelled                                     -> RED
  - unexpected shape                                                  -> AMBER
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
from tools.ekyc import EkycError, EkycInvalidInput, verify_udyam

SOURCE_NAME = "eKYC Now (Udyam)"

_VALID_CATEGORIES = {"MICRO", "SMALL", "MEDIUM"}


def screen_udyam(vendor: VendorIntake, api_key: str, customer_id: str) -> list[EvidenceRecord]:
    if vendor.entity_type == EntityType.FOREIGN_ENTITY:
        return []
    if not vendor.udyam_number:
        return []
    if not api_key or not customer_id:
        return []

    try:
        payload = verify_udyam(vendor.udyam_number, api_key, customer_id)
    except EkycInvalidInput as exc:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=vendor.udyam_number,
                summary=f"Udyam number '{vendor.udyam_number}' rejected: {exc}.",
                tag=FindingTag.RESOLVED_RED_FLAG,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url="https://udyamregistration.gov.in/Udyam_Verify.aspx",
            )
        ]
    except EkycError as exc:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference="technical-failure",
                summary=f"Udyam lookup failed: {exc}. Retry needed.",
                tag=FindingTag.UNRESOLVED,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.TECHNICAL_FAILURE,
            )
        ]

    status = str(payload.get("status", "")).strip().upper()
    enterprise_type = str(payload.get("enterprise_type", "")).strip().upper()
    enterprise_name = payload.get("enterprise_name") or vendor.name
    citation_url = payload.get("udyam_certificate_url") or "https://udyamregistration.gov.in/Udyam_Verify.aspx"

    if status != "SUCCESS":
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=vendor.udyam_number,
                summary=(
                    f"Udyam number '{vendor.udyam_number}' returned non-success "
                    f"status '{status}' — likely not registered or cancelled."
                ),
                tag=FindingTag.RESOLVED_RED_FLAG,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url=citation_url,
            )
        ]

    if enterprise_type in _VALID_CATEGORIES:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.INDIA_REGULATORY,
                source_name=SOURCE_NAME,
                source_reference=payload.get("udyam_number", vendor.udyam_number),
                summary=(
                    f"Udyam confirms '{enterprise_name}' as a {enterprise_type.title()} "
                    "enterprise. Eligible for MSMED 45-day payment protection."
                ),
                tag=FindingTag.RESOLVED_CLEAN,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url=citation_url,
                supporting_citations=[
                    SupportingCitation(
                        title=f"Udyam certificate — {enterprise_name}",
                        url=citation_url,
                        source="udyamregistration.gov.in",
                    )
                ],
            )
        ]

    return [
        EvidenceRecord(
            vendor_id=vendor.vendor_id,
            category=FindingCategory.INDIA_REGULATORY,
            source_name=SOURCE_NAME,
            source_reference=payload.get("udyam_number", vendor.udyam_number),
            summary=(
                f"Udyam returned registered status but enterprise_type "
                f"'{enterprise_type}' is unexpected — analyst to verify."
            ),
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_1,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url=citation_url,
        )
    ]
