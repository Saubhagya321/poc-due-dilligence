from agents.entity_resolution import screen_entity_resolution
from agents.evidence_guardrail import review_evidence_citations
from agents.global_compliance import screen_global_compliance
from agents.gst_registry import screen_gst
from agents.litigation import screen_litigation
from agents.mca_cin import screen_mca
from agents.nclt_ibbi import screen_nclt_ibbi
from agents.scoring import score_vendor
from agents.udyam_registry import screen_udyam
from orchestrator.orchestrator import build_report
from schemas.evidence import EvidenceRecord
from schemas.report import Report, ReportField, ScoringResult
from schemas.vendor import VendorIntake
from tools.ibbi import CirpDataset

# Loaded once at import time; the TSV is ~4.6MB and ~15k rows, cheap to
# keep resident. Refreshed by scripts/scrape_ibbi.py on a weekly cron.
_IBBI_DATASET = CirpDataset.from_path()


def _accepted_findings(
    vendor: VendorIntake,
    opensanctions_api_key: str,
    tavily_api_key: str,
    indian_kanoon_api_key: str,
    ekyc_api_key: str = "",
    ekyc_customer_id: str = "",
    manual_findings: list[EvidenceRecord] | None = None,
) -> list[EvidenceRecord]:
    """
    Entity resolution + global compliance + litigation + eKYC KYB tiles
    (CIN/GST/Udyam when supplied) + whatever an analyst has submitted
    for the still-manual checks (EPFO, ESIC, SFIO, SEBI, NSE, BSE, ...)
    -> citation guardrail.
    """
    findings = (
        screen_entity_resolution(
            vendor, ekyc_api_key=ekyc_api_key, ekyc_customer_id=ekyc_customer_id
        )
        + screen_global_compliance(
            vendor=vendor,
            opensanctions_api_key=opensanctions_api_key,
            tavily_api_key=tavily_api_key,
        )
        + screen_litigation(
            vendor=vendor,
            indian_kanoon_api_key=indian_kanoon_api_key,
        )
        + screen_mca(vendor, api_key=ekyc_api_key, customer_id=ekyc_customer_id)
        + screen_gst(vendor, api_key=ekyc_api_key, customer_id=ekyc_customer_id)
        + screen_udyam(vendor, api_key=ekyc_api_key, customer_id=ekyc_customer_id)
        + screen_nclt_ibbi(vendor, _IBBI_DATASET)
        + (manual_findings or [])
    )
    accepted, _rejected = review_evidence_citations(findings)
    return accepted


def run_vendor_screening(
    vendor: VendorIntake,
    opensanctions_api_key: str,
    tavily_api_key: str,
    indian_kanoon_api_key: str,
    ekyc_api_key: str = "",
    ekyc_customer_id: str = "",
    manual_findings: list[EvidenceRecord] | None = None,
) -> ScoringResult:
    """Intake -> agents -> citation guardrail -> scoring."""
    accepted = _accepted_findings(
        vendor,
        opensanctions_api_key,
        tavily_api_key,
        indian_kanoon_api_key,
        ekyc_api_key,
        ekyc_customer_id,
        manual_findings,
    )
    return score_vendor(vendor_id=vendor.vendor_id, records=accepted)


def run_vendor_screening_report(
    vendor: VendorIntake,
    routed_fields: list[ReportField],
    opensanctions_api_key: str,
    tavily_api_key: str,
    indian_kanoon_api_key: str,
    ekyc_api_key: str = "",
    ekyc_customer_id: str = "",
    manual_findings: list[EvidenceRecord] | None = None,
) -> Report:
    """Same pipeline as run_vendor_screening, but returns the full per-check Report."""
    accepted = _accepted_findings(
        vendor,
        opensanctions_api_key,
        tavily_api_key,
        indian_kanoon_api_key,
        ekyc_api_key,
        ekyc_customer_id,
        manual_findings,
    )
    scoring = score_vendor(vendor_id=vendor.vendor_id, records=accepted)
    return build_report(
        vendor_id=vendor.vendor_id,
        routed_fields=routed_fields,
        records=accepted,
        score=scoring.score,
        recommendation=scoring.recommendation.value,
        score_reasons=scoring.reasons,
    )
