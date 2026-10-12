"""
Seam under test: orchestrator.build_report(vendor_id, routed_fields, records,
scoring_result) — turns the intake routing decisions + the evidence records
actually produced by the pipeline + the final score into the report screen
the analyst reads at the end.

Colour rules per field:
- selected=False               -> grey, reason stays whatever route_checks/
                                   apply_overrides said (not selected)
- applicable=False             -> grey (nothing could have run)
- selected + applicable, but no matching EvidenceRecord came back
  (category not implemented yet / check not wired up)   -> grey, reason
  says it didn't run
- matching record tag resolved-clean / confirmed-by-absence  -> green
- matching record tag resolved-red-flag                       -> red
- matching record tag unresolved / vendor-declared             -> amber

Only litigation and global compliance are wired to real agents right now,
so this test exercises the source-based mapping (OpenSanctions ->
SANCTIONS_PEP, Tavily web search -> ADVERSE_MEDIA, Indian Kanoon ->
ECOURTS) and confirms every other still-selected-but-unimplemented check
falls back to grey with a "check not yet run" reason rather than silently
vanishing from the report.
"""
from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)
from schemas.report import CanonicalCheck, CheckStatusColor
from schemas.vendor import EntityType
from agents.manual_findings import record_manual_finding
from orchestrator.orchestrator import build_report, route_checks


def test_supporting_citations_from_a_record_are_surfaced_on_its_report_field():
    # Indian Kanoon can return multiple same-name cases; the analyst needs
    # each one's citation URL on the eCourts tile, not just the top match.
    from schemas.evidence import SupportingCitation

    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    records = [
        EvidenceRecord(
            vendor_id="v1",
            category=FindingCategory.LITIGATION,
            source_name="Indian Kanoon",
            source_reference="111",
            summary="Pattern flag: 3 cases",
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url="https://indiankanoon.org/doc/111/",
            supporting_citations=[
                SupportingCitation(title="Case A", url="https://indiankanoon.org/doc/111/", source="Court 1"),
                SupportingCitation(title="Case B", url="https://indiankanoon.org/doc/222/", source="Court 2"),
            ],
        )
    ]

    report = build_report(vendor_id="v1", routed_fields=fields, records=records, score=50.0, recommendation="proceed-with-safeguards")

    ecourts = next(f for f in report.fields if f.check == CanonicalCheck.ECOURTS)
    assert len(ecourts.supporting_citations) == 2
    assert ecourts.supporting_citations[1].url == "https://indiankanoon.org/doc/222/"


def test_build_report_surfaces_score_reasons_from_scoring_result():
    # The scoring agent already builds a reasons list naming every
    # unresolved/vendor-declared/red-flag finding driving the score.
    # Report threw it away before — analyst saw a number with no "why".
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    reasons = ["Unresolved, needs human review: foo", "Vendor did not provide: bar"]

    report = build_report(
        vendor_id="v1",
        routed_fields=fields,
        records=[],
        score=55.0,
        recommendation="proceed-with-safeguards",
        score_reasons=reasons,
    )

    assert report.score_reasons == reasons


def test_a_clean_global_compliance_record_turns_that_field_green_with_citation():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    records = [
        EvidenceRecord(
            vendor_id="v1",
            category=FindingCategory.GLOBAL_COMPLIANCE,
            source_name="OpenSanctions",
            source_reference="https://www.opensanctions.org/search/?q=v1",
            summary="No sanctions/PEP match found",
            tag=FindingTag.RESOLVED_CLEAN,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.SUCCESS,
            citation_url="https://www.opensanctions.org/search/?q=v1",
        )
    ]

    report = build_report(vendor_id="v1", routed_fields=fields, records=records, score=100.0, recommendation="proceed")

    gc = next(f for f in report.fields if f.check == CanonicalCheck.SANCTIONS_PEP)
    assert gc.color == CheckStatusColor.GREEN
    assert gc.citation_url == "https://www.opensanctions.org/search/?q=v1"


def test_a_red_flag_record_turns_that_field_red():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    records = [
        EvidenceRecord(
            vendor_id="v1",
            category=FindingCategory.GLOBAL_COMPLIANCE,
            source_name="OpenSanctions",
            source_reference="ref",
            summary="Sanctions match",
            tag=FindingTag.RESOLVED_RED_FLAG,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.SUCCESS,
            citation_url="https://www.opensanctions.org/entities/xyz",
        )
    ]

    report = build_report(vendor_id="v1", routed_fields=fields, records=records, score=0.0, recommendation="decline")

    gc = next(f for f in report.fields if f.check == CanonicalCheck.SANCTIONS_PEP)
    assert gc.color == CheckStatusColor.RED


def test_an_unresolved_litigation_hit_turns_ecourts_amber_with_its_citation():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    records = [
        EvidenceRecord(
            vendor_id="v1",
            category=FindingCategory.LITIGATION,
            source_name="Indian Kanoon",
            source_reference="https://example.com/article",
            summary="'Scammed by v1' — needs human cross-check",
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_3,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
            citation_url="https://example.com/article",
        )
    ]

    report = build_report(vendor_id="v1", routed_fields=fields, records=records, score=50.0, recommendation="proceed-with-safeguards")

    ecourts = next(f for f in report.fields if f.check == CanonicalCheck.ECOURTS)
    assert ecourts.color == CheckStatusColor.AMBER
    assert ecourts.citation_url == "https://example.com/article"


def test_a_deselected_check_stays_grey_even_if_it_was_applicable():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    fields = [f.model_copy(update={"selected": False}) if f.check == CanonicalCheck.GST else f for f in fields]

    report = build_report(vendor_id="v1", routed_fields=fields, records=[], score=0.0, recommendation="decline")

    gst = next(f for f in report.fields if f.check == CanonicalCheck.GST)
    assert gst.color == CheckStatusColor.GREY


def test_a_selected_applicable_check_with_no_record_yet_stays_grey_and_says_why():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)

    report = build_report(vendor_id="v1", routed_fields=fields, records=[], score=0.0, recommendation="decline")

    gst = next(f for f in report.fields if f.check == CanonicalCheck.GST)
    assert gst.color == CheckStatusColor.GREY
    assert "not yet run" in gst.reason.lower()


def test_an_analyst_manual_finding_colours_its_own_check_not_a_neighbour():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)
    record = record_manual_finding(
        vendor_id="v1",
        check=CanonicalCheck.GST,
        tag=FindingTag.RESOLVED_RED_FLAG,
        summary="GSTIN cancelled for non-filing.",
        citation_url="https://services.gst.gov.in/services/searchtp",
    )

    report = build_report(vendor_id="v1", routed_fields=fields, records=[record], score=0.0, recommendation="decline")

    gst = next(f for f in report.fields if f.check == CanonicalCheck.GST)
    assert gst.color == CheckStatusColor.RED
    assert gst.source_name == "Analyst manual entry"

    epfo = next(f for f in report.fields if f.check == CanonicalCheck.EPFO)
    assert epfo.color == CheckStatusColor.GREY


def test_a_foreign_entity_has_all_india_specific_checks_marked_not_applicable():
    fields = route_checks(entity_type=EntityType.FOREIGN_ENTITY, has_physical_premises=False)
    by_check = {f.check: f for f in fields}

    for check in (
        CanonicalCheck.PAN_VERIFICATION,
        CanonicalCheck.GST,
        CanonicalCheck.MCA,
        CanonicalCheck.SEBI,
        CanonicalCheck.NCLT,
        CanonicalCheck.EPFO,
        CanonicalCheck.ESIC,
        CanonicalCheck.SFIO,
        CanonicalCheck.RBI_CIBIL,
        CanonicalCheck.NSE,
        CanonicalCheck.BSE,
        CanonicalCheck.MSME_UDYAM,
    ):
        assert by_check[check].applicable is False, f"{check} should be not-applicable for a foreign entity"

    for check in (
        CanonicalCheck.SANCTIONS_PEP,
        CanonicalCheck.ADVERSE_MEDIA,
        CanonicalCheck.ECOURTS,
        CanonicalCheck.UBO_TRACE,
    ):
        assert by_check[check].applicable is True, f"{check} should still apply to a foreign entity"
