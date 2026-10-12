"""
Seam under test: run_vendor_screening_report(vendor, routed_fields, ...) —
same pipeline as run_vendor_screening, but returns the full per-check
Report (orchestrator.build_report) instead of just the ScoringResult, so
the API/frontend can render the colour-coded report screen instead of a
bare recommendation string.

Tavily and Indian Kanoon are mocked for the same non-determinism reasons
documented in test_vendor_screening_workflow.py; OpenSanctions is mocked
clean here since this test is about report shape, not compliance-screening
behaviour (already covered by that other test file).
"""
from decimal import Decimal

from schemas.report import CanonicalCheck, CheckStatusColor, RecommendedAction
from schemas.evidence import FindingTag
from schemas.vendor import EntityType, VendorIntake
from agents.manual_findings import record_manual_finding
from orchestrator.orchestrator import route_checks
from workflows.vendor_screening import run_vendor_screening_report


def test_vendor_a_report_has_a_green_pan_verification_and_sanctions_field(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value={"results": [], "total": {"value": 0, "relation": "eq"}},
    )
    mocker.patch("tools.tavily_search._search", return_value={"results": []})
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[])

    vendor = VendorIntake(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Enterprises",
        pan="AMMPK4657M",
        entity_type=EntityType.SOLE_PROPRIETORSHIP,
        contract_value=Decimal("500000"),
        has_physical_premises=False,
    )
    routed_fields = route_checks(
        entity_type=vendor.entity_type, has_physical_premises=vendor.has_physical_premises
    )

    report = run_vendor_screening_report(
        vendor=vendor,
        routed_fields=routed_fields,
        opensanctions_api_key="unused-because-opensanctions-is-mocked",
        tavily_api_key="unused-because-tavily-is-mocked",
        indian_kanoon_api_key="unused-because-indian-kanoon-is-mocked",
    )

    assert report.vendor_id == "vendor-a-suresh-enterprises"
    assert report.recommendation == RecommendedAction.PROCEED.value

    fields_by_check = {f.check.value: f for f in report.fields}
    assert fields_by_check["pan_verification"].color == CheckStatusColor.GREEN
    assert fields_by_check["pan_verification"].source_name == "PAN format check"
    assert fields_by_check["sanctions_pep"].color == CheckStatusColor.GREEN
    assert fields_by_check["sanctions_pep"].source_name == "OpenSanctions"


def test_an_analyst_submitted_manual_finding_shows_up_in_the_report(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value={"results": [], "total": {"value": 0, "relation": "eq"}},
    )
    mocker.patch("tools.tavily_search._search", return_value={"results": []})
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[])

    vendor = VendorIntake(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Enterprises",
        pan="AMMPK4657M",
        entity_type=EntityType.SOLE_PROPRIETORSHIP,
        contract_value=Decimal("500000"),
        has_physical_premises=False,
    )
    routed_fields = route_checks(
        entity_type=vendor.entity_type, has_physical_premises=vendor.has_physical_premises
    )
    manual_finding = record_manual_finding(
        vendor_id=vendor.vendor_id,
        check=CanonicalCheck.GST,
        tag=FindingTag.RESOLVED_CLEAN,
        summary="GSTIN Active, no defaults on record.",
        citation_url="https://services.gst.gov.in/services/searchtp",
    )

    report = run_vendor_screening_report(
        vendor=vendor,
        routed_fields=routed_fields,
        opensanctions_api_key="unused-because-opensanctions-is-mocked",
        tavily_api_key="unused-because-tavily-is-mocked",
        indian_kanoon_api_key="unused-because-indian-kanoon-is-mocked",
        manual_findings=[manual_finding],
    )

    fields_by_check = {f.check.value: f for f in report.fields}
    assert fields_by_check["gst"].color == CheckStatusColor.GREEN
    assert fields_by_check["gst"].source_name == "Analyst manual entry"
