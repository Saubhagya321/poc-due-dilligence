from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)
from schemas.vendor import EntityType, VendorIntake
from tools.ekyc import EkycError, EkycInvalidInput, verify_pan_sync


def screen_entity_resolution(
    vendor: VendorIntake,
    ekyc_api_key: str = "",
    ekyc_customer_id: str = "",
) -> list[EvidenceRecord]:
    """
    PAN verification.

    Default path (eKYC credentials not configured): format-only check — the
    intake validator already rejected a malformed PAN before we got here,
    so we record that fact as a citable TIER_4 (vendor-self-disclosure)
    finding.

    Upgraded path (eKYC credentials present): hits NSDL via Message Central's
    /pan/sync-verify. Confirms the PAN exists AND the registered name matches
    the vendor's declared name, with a TIER_1 (official registry) finding.

    A foreign entity has no Indian PAN — not applicable either way.
    """
    if vendor.entity_type == EntityType.FOREIGN_ENTITY:
        return []

    # Fallback: no eKYC credentials -> original format-only finding
    if not ekyc_api_key or not ekyc_customer_id:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.ENTITY_RESOLUTION,
                source_name="PAN format check",
                source_reference="pan",
                summary=f"PAN {vendor.pan} matches the expected Indian PAN format (format check only, not a government identity verification).",
                tag=FindingTag.RESOLVED_CLEAN,
                confidence_tier=ConfidenceTier.TIER_4,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
            )
        ]

    # Live existence + name-match check
    try:
        payload = verify_pan_sync(vendor.pan, ekyc_api_key, ekyc_customer_id)
    except EkycInvalidInput as exc:
        # Format passed but eKYC rejected the PAN — e.g. deactivated or never issued
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.ENTITY_RESOLUTION,
                source_name="eKYC Now (PAN)",
                source_reference=vendor.pan,
                summary=(
                    f"PAN {vendor.pan} rejected by NSDL: {exc}. Format was valid "
                    "but the PAN does not resolve to a live NSDL record."
                ),
                tag=FindingTag.RESOLVED_RED_FLAG,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url="https://www.incometax.gov.in/iec/foportal/",
            )
        ]
    except EkycError as exc:
        # Network / 5xx — fall back to the format-only finding + a note
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.ENTITY_RESOLUTION,
                source_name="PAN format check",
                source_reference="pan",
                summary=(
                    f"PAN {vendor.pan} passed format check. NSDL live-verify "
                    f"temporarily unavailable ({exc}); retry recommended."
                ),
                tag=FindingTag.UNRESOLVED,
                confidence_tier=ConfidenceTier.TIER_4,
                as_of_date=date.today(),
                check_status=CheckStatus.TECHNICAL_FAILURE,
            )
        ]

    is_valid = payload.get("valid") is True or str(payload.get("pan_status", "")).upper() == "VALID"
    name_pan = payload.get("name_pan_card") or payload.get("registered_name") or ""
    # name_match_result/score may be absent if NSDL returned the record without
    # a match comparison — surface what we have.
    name_match = str(payload.get("name_match_result", "")).upper()
    name_score = payload.get("name_match_score")

    if not is_valid:
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.ENTITY_RESOLUTION,
                source_name="eKYC Now (PAN)",
                source_reference=vendor.pan,
                summary=(
                    f"NSDL does not confirm PAN {vendor.pan} as valid "
                    f"(message: {payload.get('message', 'unknown')})."
                ),
                tag=FindingTag.RESOLVED_RED_FLAG,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url="https://www.incometax.gov.in/iec/foportal/",
            )
        ]

    # Valid PAN + name verification
    name_note = f"Registered name: '{name_pan}'."
    if name_match in {"Y", "YES", "MATCH"} or (isinstance(name_score, (int, float)) and name_score >= 80):
        return [
            EvidenceRecord(
                vendor_id=vendor.vendor_id,
                category=FindingCategory.ENTITY_RESOLUTION,
                source_name="eKYC Now (PAN)",
                source_reference=vendor.pan,
                summary=(
                    f"NSDL confirms PAN {vendor.pan} is VALID and the registered "
                    f"name matches the declared vendor name. {name_note}"
                ),
                tag=FindingTag.RESOLVED_CLEAN,
                confidence_tier=ConfidenceTier.TIER_1,
                as_of_date=date.today(),
                check_status=CheckStatus.SUCCESS,
                citation_url="https://www.incometax.gov.in/iec/foportal/",
            )
        ]

    # PAN valid but name doesn't match — common when a vendor is onboarded
    # under a trade name while the PAN is registered under the legal name.
    # Not auto-red because this is often legitimate; amber for analyst review.
    return [
        EvidenceRecord(
            vendor_id=vendor.vendor_id,
            category=FindingCategory.ENTITY_RESOLUTION,
            source_name="eKYC Now (PAN)",
            source_reference=vendor.pan,
            summary=(
                f"PAN {vendor.pan} is VALID per NSDL but the registered name "
                f"'{name_pan}' does not clearly match the declared vendor name "
                f"'{vendor.name}' — analyst to confirm identity."
            ),
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_1,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url="https://www.incometax.gov.in/iec/foportal/",
        )
    ]
