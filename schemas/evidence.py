from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator


class FindingCategory(str, Enum):
    ENTITY_RESOLUTION = "entity_resolution"
    GLOBAL_COMPLIANCE = "global_compliance"
    INDIA_REGULATORY = "india_regulatory"
    LITIGATION = "litigation"
    OWNERSHIP_BEHAVIOUR = "ownership_behaviour"


class FindingTag(str, Enum):
    RESOLVED_CLEAN = "resolved-clean"
    RESOLVED_RED_FLAG = "resolved-red-flag"
    VENDOR_DECLARED = "vendor-declared"
    UNRESOLVED = "unresolved"
    CONFIRMED_BY_ABSENCE = "confirmed-by-absence"


class ConfidenceTier(int, Enum):
    TIER_1 = 1  # official registry or licensed credit bureau, queried directly
    TIER_2 = 2  # licensed aggregator that cites its own underlying source
    TIER_3 = 3  # aggregator/scraper with no exposed provenance
    TIER_4 = 4  # vendor self-disclosure


class CheckStatus(str, Enum):
    SUCCESS = "success"
    TECHNICAL_FAILURE = "technical_failure"
    AMBIGUOUS_MATCH = "ambiguous_match"


class SupportingCitation(BaseModel):
    """
    A secondary citation attached to an EvidenceRecord. Indian Kanoon can
    return multiple same-name cases for a common vendor name; each one
    needs its own URL so the analyst can click through and confirm which
    (if any) actually relate to this vendor vs. a different same-named party.
    """

    title: str
    url: str
    source: str


class EvidenceRecord(BaseModel):
    vendor_id: str
    category: FindingCategory
    source_name: str
    source_reference: str
    summary: str
    tag: FindingTag
    confidence_tier: ConfidenceTier
    as_of_date: date
    check_status: CheckStatus
    citation_url: Optional[str] = None
    supporting_citations: list[SupportingCitation] = []

    @model_validator(mode="after")
    def technical_failure_cannot_be_clean(self) -> "EvidenceRecord":
        if self.check_status == CheckStatus.TECHNICAL_FAILURE and self.tag == FindingTag.RESOLVED_CLEAN:
            raise ValueError(
                "A technical failure can never be recorded as resolved-clean — "
                "retry or flag it, don't silently mark it clean."
            )
        return self
