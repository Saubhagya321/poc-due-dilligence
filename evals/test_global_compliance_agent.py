"""
Seam under test: screen_global_compliance(vendor, opensanctions_api_key,
tavily_api_key) — the public entry point the orchestrator calls to run every
global-compliance check for one vendor.

This agent has no logic of its own worth testing in isolation from its
tools — its whole job is "call sanctions_pep_screen and adverse_media_search,
hand back both findings". So we mock those two tools (already covered by
their own real-fixture-backed tests) and check the agent wires them
together and doesn't drop a result.
"""
from datetime import date
from decimal import Decimal

from agents.global_compliance import screen_global_compliance
from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)
from schemas.vendor import EntityType, VendorIntake

VENDOR = VendorIntake(
    vendor_id="vendor-a-suresh-enterprises",
    name="Suresh Enterprises",
    pan="AMMPK4657M",
    entity_type=EntityType.SOLE_PROPRIETORSHIP,
    contract_value=Decimal("500000"),
    has_physical_premises=False,
)


def _fake_record(source_name: str, tag=FindingTag.RESOLVED_CLEAN, summary="fake summary") -> EvidenceRecord:
    return EvidenceRecord(
        vendor_id=VENDOR.vendor_id,
        category=FindingCategory.GLOBAL_COMPLIANCE,
        source_name=source_name,
        source_reference="fake-ref",
        summary=summary,
        tag=tag,
        confidence_tier=ConfidenceTier.TIER_2,
        as_of_date=date.today(),
        check_status=CheckStatus.SUCCESS,
        citation_url="https://www.opensanctions.org/entities/x/",
    )


def test_nse_debarred_sanctions_hit_also_emits_an_nse_tile_record(mocker):
    # OpenSanctions already pulls the NSE debarred list — when a vendor hits
    # that specific dataset we should populate the NSE tile too, not just
    # the sanctions tile.
    nse_hit = _fake_record(
        "OpenSanctions",
        tag=FindingTag.RESOLVED_RED_FLAG,
        summary="Matched 'X' in datasets: in_nse_debarred.",
    )
    mocker.patch("agents.global_compliance.sanctions_pep_screen", return_value=nse_hit)
    mocker.patch("agents.global_compliance.adverse_media_search", return_value=_fake_record("Tavily web search"))

    findings = screen_global_compliance(VENDOR, "k", "k")

    nse_records = [f for f in findings if f.source_name == "OpenSanctions (NSE debarred)"]
    assert len(nse_records) == 1
    assert nse_records[0].tag == FindingTag.RESOLVED_RED_FLAG


def test_non_nse_sanctions_hit_does_not_emit_nse_tile_record(mocker):
    ofac_hit = _fake_record(
        "OpenSanctions",
        tag=FindingTag.RESOLVED_RED_FLAG,
        summary="Matched 'X' in datasets: us_ofac_sdn.",
    )
    mocker.patch("agents.global_compliance.sanctions_pep_screen", return_value=ofac_hit)
    mocker.patch("agents.global_compliance.adverse_media_search", return_value=_fake_record("Tavily web search"))

    findings = screen_global_compliance(VENDOR, "k", "k")

    assert all(f.source_name != "OpenSanctions (NSE debarred)" for f in findings)


def test_clean_sanctions_does_not_emit_nse_record(mocker):
    mocker.patch("agents.global_compliance.sanctions_pep_screen", return_value=_fake_record("OpenSanctions"))
    mocker.patch("agents.global_compliance.adverse_media_search", return_value=_fake_record("Tavily web search"))

    findings = screen_global_compliance(VENDOR, "k", "k")

    assert all(f.source_name != "OpenSanctions (NSE debarred)" for f in findings)


def test_runs_both_tools_and_returns_both_findings(mocker):
    sanctions_record = _fake_record("OpenSanctions")
    media_record = _fake_record("Tavily web search")

    mock_sanctions = mocker.patch(
        "agents.global_compliance.sanctions_pep_screen", return_value=sanctions_record
    )
    mock_media = mocker.patch(
        "agents.global_compliance.adverse_media_search", return_value=media_record
    )

    findings = screen_global_compliance(
        vendor=VENDOR,
        opensanctions_api_key="fake-os-key",
        tavily_api_key="fake-tavily-key",
    )

    assert findings == [sanctions_record, media_record]
    mock_sanctions.assert_called_once_with(
        vendor_id=VENDOR.vendor_id, name=VENDOR.name, pan=VENDOR.pan, api_key="fake-os-key"
    )
    mock_media.assert_called_once_with(
        vendor_id=VENDOR.vendor_id, name=VENDOR.name, api_key="fake-tavily-key"
    )


def test_key_persons_are_also_screened_against_opensanctions(mocker):
    # Promoters/directors can be sanctioned/PEP even when the entity name
    # isn't (Mehul Choksi hits OFAC, "Gitanjali Gems Limited" doesn't).
    # This is a real product gap we're closing.
    from schemas.evidence import SupportingCitation

    vendor = VendorIntake(
        vendor_id="vendor-gitanjali",
        name="Gitanjali Gems Limited",
        pan="AAACG1642F",
        entity_type=EntityType.PUBLIC_LIMITED,
        contract_value=Decimal("10000000"),
        has_physical_premises=True,
        key_persons=["Mehul Choksi"],
    )

    entity_clean = _fake_record("OpenSanctions")  # entity itself clean
    person_hit = EvidenceRecord(
        vendor_id=vendor.vendor_id,
        category=FindingCategory.GLOBAL_COMPLIANCE,
        source_name="OpenSanctions",
        source_reference="person-match-id",
        summary="Matched 'Mehul Choksi' on sanctions list",
        tag=FindingTag.RESOLVED_RED_FLAG,
        confidence_tier=ConfidenceTier.TIER_2,
        as_of_date=date.today(),
        check_status=CheckStatus.SUCCESS,
        citation_url="https://www.opensanctions.org/entities/person-match-id",
    )

    def fake_sanctions(vendor_id, name, pan, api_key):
        return person_hit if name == "Mehul Choksi" else entity_clean

    mocker.patch("agents.global_compliance.sanctions_pep_screen", side_effect=fake_sanctions)
    mocker.patch("agents.global_compliance.adverse_media_search", return_value=_fake_record("Tavily web search"))

    findings = screen_global_compliance(
        vendor=vendor,
        opensanctions_api_key="fake-os-key",
        tavily_api_key="fake-tavily-key",
    )

    sanctions = next(f for f in findings if f.source_name == "OpenSanctions")
    # Worst-tag-wins: person hit RED should promote the combined record to RED.
    assert sanctions.tag == FindingTag.RESOLVED_RED_FLAG
    # Both the entity and the key person screening results should be visible.
    titles = [c.title for c in sanctions.supporting_citations]
    assert "Gitanjali Gems Limited" in titles
    assert "Mehul Choksi" in titles
