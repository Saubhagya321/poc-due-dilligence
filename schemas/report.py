from enum import Enum
from typing import Optional

from pydantic import BaseModel

from schemas.evidence import SupportingCitation


class RecommendedAction(str, Enum):
    PROCEED = "proceed"
    PROCEED_WITH_SAFEGUARDS = "proceed-with-safeguards"
    DECLINE = "decline"


class ScoringResult(BaseModel):
    vendor_id: str
    recommendation: RecommendedAction
    score: float
    reasons: list[str]


class CanonicalCheck(str, Enum):
    """
    The spec's 21 checks: 17 data-fetch checks + 4 reasoning-only checks
    derived from data already collected by the fetch checks (no new API
    call of their own). See DERIVED_CHECKS below for the latter group.
    """

    # Entity resolution
    PAN_VERIFICATION = "pan_verification"

    # Global compliance
    SANCTIONS_PEP = "sanctions_pep"
    ADVERSE_MEDIA = "adverse_media"

    # India regulatory
    GST = "gst"
    MCA = "mca"
    SEBI = "sebi"
    NCLT = "nclt"
    EPFO = "epfo"
    ESIC = "esic"
    SFIO = "sfio"
    RBI_CIBIL = "rbi_cibil"
    NSE = "nse"
    BSE = "bse"
    MSME_UDYAM = "msme_udyam"
    FACTORY_TRADE_LICENCE = "factory_trade_licence"

    # Litigation
    ECOURTS = "ecourts"

    # Ownership
    UBO_TRACE = "ubo_trace"

    # Reasoning-only — derived from the checks above, no new fetch
    FILING_DISCIPLINE = "filing_discipline"
    OPERATING_TENURE = "operating_tenure"
    TURNOVER_BAND = "turnover_band"
    LICENCE_DOCUMENT_GAPS = "licence_document_gaps"


DERIVED_CHECKS = {
    CanonicalCheck.FILING_DISCIPLINE,
    CanonicalCheck.OPERATING_TENURE,
    CanonicalCheck.TURNOVER_BAND,
    CanonicalCheck.LICENCE_DOCUMENT_GAPS,
}


class CheckStatusColor(str, Enum):
    GREEN = "green"  # accepted: resolved-clean / confirmed-by-absence
    RED = "red"  # rejected: resolved-red-flag
    GREY = "grey"  # not selected by the analyst at intake
    AMBER = "amber"  # ran, but unresolved / vendor-declared — needs a human


class ReportField(BaseModel):
    check: CanonicalCheck
    applicable: bool
    selected: bool
    color: CheckStatusColor
    reason: str
    source_name: Optional[str] = None
    citation_url: Optional[str] = None
    supporting_citations: list[SupportingCitation] = []


class Report(BaseModel):
    vendor_id: str
    fields: list[ReportField]
    score: float
    recommendation: str
    score_reasons: list[str] = []


class ManualChecklistTask(BaseModel):
    check: CanonicalCheck
    instruction: str
    portal_hint: str
