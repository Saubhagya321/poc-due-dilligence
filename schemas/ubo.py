"""
Ownership graph for the UBO trace tile. Different shape from a normal
manual finding — this is a tree, not a sentence — but it still gets
locked as an EvidenceRecord so the orchestrator / scoring pipeline
doesn't need any special-case handling.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# Entity types the extractor can emit. Downstream colouring uses these:
# natural_person + Indian = terminal clean leaf; foreign_entity = amber;
# trust / huf / unknown = amber (needs more tracing); listed /
# government = terminal clean (exempt from further trace).
ENTITY_TYPES = {
    "natural_person",
    "company",
    "llp",
    "trust",
    "huf",
    "listed",
    "government",
    "foreign_entity",
    "unknown",
}


class OwnershipNode(BaseModel):
    name: str
    # % stake this node holds in its PARENT (not in its children).
    # None at the root (the vendor itself) because nobody holds the vendor.
    stake_pct: Optional[float] = None
    entity_type: str = "unknown"
    jurisdiction: Optional[str] = None  # "India" / country name / None if unclear
    children: list["OwnershipNode"] = []  # one layer up (this node's owners)
    note: Optional[str] = None  # any clarifying text the extractor or analyst added


class OwnershipGraph(BaseModel):
    vendor_root: OwnershipNode
    raw_source: str  # "document:MGT7.pdf" or "analyst-text" or combined
    analyst_notes: str = ""  # free-form, editable before lock


OwnershipNode.model_rebuild()
