"""
NCLT tile — automated via a locally-scraped IBBI public-announcement
dataset (see tools/ibbi.py).

Why this exists: eCourts India LegalCheck covers NCLT at ~Rs.99/vendor,
which blows the per-vendor budget for a POC. IBBI publishes every CIRP
public announcement; downloading that list weekly gives us ~90% of the
real NCLT signal (companies currently in insolvency) at zero marginal
cost. Pre-admission petitions still need LegalCheck.

Routing:
  - Only applicable to NCLT-eligible entities (Companies Act + LLPs),
    matching the orchestrator's own gate on CanonicalCheck.NCLT.
  - Prefers CIN match (bulletproof) over name match (fuzzy but still
    useful when vendor didn't supply a CIN).
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
from tools.ibbi import CirpDataset, CirpRecord

SOURCE_NAME = "IBBI CIRP dataset"
IBBI_PA_URL = "https://ibbi.gov.in/public-announcement"

_APPLICABLE_TYPES = {
    EntityType.LLP,
    EntityType.OPC,
    EntityType.PRIVATE_LIMITED,
    EntityType.PUBLIC_LIMITED,
}


def _red_record(vendor: VendorIntake, hit: CirpRecord, matched_on: str) -> EvidenceRecord:
    return EvidenceRecord(
        vendor_id=vendor.vendor_id,
        category=FindingCategory.LITIGATION,
        source_name=SOURCE_NAME,
        source_reference=hit.cin or hit.corporate_debtor,
        summary=(
            f"IBBI lists '{hit.corporate_debtor}' under an active insolvency "
            f"process ({hit.announcement_type}, announced {hit.date_of_announcement}, "
            f"applicant {hit.applicant}). Matched on {matched_on}."
        ),
        tag=FindingTag.RESOLVED_RED_FLAG,
        confidence_tier=ConfidenceTier.TIER_1,
        as_of_date=date.today(),
        check_status=CheckStatus.SUCCESS,
        citation_url=IBBI_PA_URL,
    )


def _clean_record(vendor: VendorIntake) -> EvidenceRecord:
    return EvidenceRecord(
        vendor_id=vendor.vendor_id,
        category=FindingCategory.LITIGATION,
        source_name=SOURCE_NAME,
        source_reference="no-match",
        summary=(
            f"No IBBI public announcement found for '{vendor.name}' "
            f"(CIN: {vendor.cin or 'not supplied'}). No active NCLT insolvency "
            f"process on record."
        ),
        tag=FindingTag.RESOLVED_CLEAN,
        confidence_tier=ConfidenceTier.TIER_1,
        as_of_date=date.today(),
        check_status=CheckStatus.SUCCESS,
        citation_url=IBBI_PA_URL,
    )


def screen_nclt_ibbi(vendor: VendorIntake, dataset: CirpDataset) -> list[EvidenceRecord]:
    if vendor.entity_type not in _APPLICABLE_TYPES:
        return []

    hit = dataset.find_by_cin(vendor.cin)
    if hit is not None:
        return [_red_record(vendor, hit, matched_on=f"CIN {vendor.cin}")]

    name_hits = dataset.find_by_name(vendor.name)
    if name_hits:
        return [_red_record(vendor, name_hits[0], matched_on=f"name '{vendor.name}'")]

    return [_clean_record(vendor)]
