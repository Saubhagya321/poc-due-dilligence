"""
Seam under test: screen_entity_resolution(vendor) -> list[EvidenceRecord].

Real-time NSDL/Protean PAN verification requires a paid aggregator, which
the project has ruled out (no KYB aggregator spend). VendorIntake's own
pydantic validator already rejects a malformed PAN before a VendorIntake
object can even be constructed (schemas/vendor.py's PAN_PATTERN check), so
by the time a vendor reaches this agent its PAN is guaranteed to be
well-formed. This check exists to put that fact on the record as its own
citable finding (PAN_VERIFICATION) rather than leaving it implicit — it is
intentionally format-only and says so in its summary and confidence tier,
so nobody downstream mistakes it for a real government identity check.
"""
from schemas.evidence import ConfidenceTier, FindingTag
from schemas.vendor import EntityType, VendorIntake
from agents.entity_resolution import screen_entity_resolution


def test_a_wellformed_pan_produces_one_resolved_clean_format_only_record():
    vendor = VendorIntake(
        vendor_id="v1",
        name="Suresh Enterprises",
        pan="AMMPK4657M",
        entity_type=EntityType.SOLE_PROPRIETORSHIP,
        contract_value=500000,
        has_physical_premises=False,
    )

    records = screen_entity_resolution(vendor)

    assert len(records) == 1
    record = records[0]
    assert record.tag == FindingTag.RESOLVED_CLEAN
    assert record.source_name == "PAN format check"
    assert "AMMPK4657M" in record.summary
    assert "format" in record.summary.lower()
    assert record.confidence_tier == ConfidenceTier.TIER_4


def test_a_foreign_entity_with_no_pan_produces_no_pan_check_record():
    # PAN verification is not applicable to a foreign entity (no Indian
    # PAN to check) — orchestrator._applicability already marks this
    # check not-applicable for FOREIGN_ENTITY, so the agent should emit
    # nothing here rather than crash on a None pan or fabricate a record.
    vendor = VendorIntake(
        vendor_id="vendor-foreign-micron",
        name="Micron Technology, Inc.",
        entity_type=EntityType.FOREIGN_ENTITY,
        contract_value=50000000,
        has_physical_premises=False,
    )

    records = screen_entity_resolution(vendor)

    assert records == []
