"""
Seam under test: score_vendor(vendor_id, records) — turns the accepted
findings for a vendor into a recommendation.

Two rules from the plan:
- A sanctions/PEP match is a hard override: decline, no matter what else
  looks clean. Money laundering / terror financing risk isn't something a
  good score elsewhere should be able to outweigh.
- Otherwise, each of the four finding categories contributes weighted
  points toward a proceed / proceed-with-safeguards / decline score.
"""
from datetime import date

from agents.scoring import score_vendor
from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)
from schemas.report import RecommendedAction


def _record(
    category: FindingCategory,
    tag: FindingTag,
    source_name: str = "OpenSanctions",
) -> EvidenceRecord:
    return EvidenceRecord(
        vendor_id="vendor-under-test",
        category=category,
        source_name=source_name,
        source_reference="fake-ref",
        summary=f"{source_name} finding",
        tag=tag,
        confidence_tier=ConfidenceTier.TIER_2,
        as_of_date=date.today(),
        check_status=CheckStatus.SUCCESS,
    )


def test_a_sanctions_match_forces_decline_regardless_of_other_clean_findings():
    records = [
        _record(FindingCategory.GLOBAL_COMPLIANCE, FindingTag.RESOLVED_RED_FLAG, "OpenSanctions"),
        _record(FindingCategory.INDIA_REGULATORY, FindingTag.RESOLVED_CLEAN, "MCA"),
        _record(FindingCategory.LITIGATION, FindingTag.RESOLVED_CLEAN, "Indian Kanoon"),
        _record(FindingCategory.OWNERSHIP_BEHAVIOUR, FindingTag.RESOLVED_CLEAN, "MCA"),
    ]

    result = score_vendor(vendor_id="vendor-under-test", records=records)

    assert result.recommendation == RecommendedAction.DECLINE
    assert result.score == 0.0


def test_a_partial_run_checking_only_two_categories_still_scores_full_on_those_two():
    # Day 1 only runs global compliance (which itself checks 2 categories:
    # global_compliance via OpenSanctions, litigation via Tavily). Scoring
    # shouldn't punish a vendor for categories that were never checked yet —
    # it should score against what was actually run.
    records = [
        _record(FindingCategory.GLOBAL_COMPLIANCE, FindingTag.RESOLVED_CLEAN, "OpenSanctions"),
        _record(FindingCategory.LITIGATION, FindingTag.CONFIRMED_BY_ABSENCE, "Tavily web search"),
    ]

    result = score_vendor(vendor_id="vendor-under-test", records=records)

    assert result.score == 100.0
    assert result.recommendation == RecommendedAction.PROCEED


def test_an_unresolved_finding_blocks_a_clean_proceed_even_if_the_score_clears_the_bar():
    # Found live: a category with one clean record (e.g. no adverse media)
    # and one unresolved record (e.g. a litigation pattern needing human
    # review) can still average out above the proceed threshold once mixed
    # with other clean categories. An unresolved finding means a human
    # hasn't confirmed it yet — a high score shouldn't be able to silently
    # wave that through as a clean proceed. It should cap at
    # proceed-with-safeguards until a human clears it.
    records = [
        _record(FindingCategory.GLOBAL_COMPLIANCE, FindingTag.RESOLVED_CLEAN, "OpenSanctions"),
        _record(FindingCategory.LITIGATION, FindingTag.CONFIRMED_BY_ABSENCE, "Tavily web search"),
        _record(FindingCategory.LITIGATION, FindingTag.UNRESOLVED, "Indian Kanoon"),
    ]

    result = score_vendor(vendor_id="vendor-under-test", records=records)

    assert result.score >= 75.0
    assert result.recommendation == RecommendedAction.PROCEED_WITH_SAFEGUARDS


def test_all_clean_findings_across_every_category_scores_full_and_proceeds():
    records = [
        _record(FindingCategory.GLOBAL_COMPLIANCE, FindingTag.RESOLVED_CLEAN, "OpenSanctions"),
        _record(FindingCategory.INDIA_REGULATORY, FindingTag.RESOLVED_CLEAN, "MCA"),
        _record(FindingCategory.LITIGATION, FindingTag.RESOLVED_CLEAN, "Indian Kanoon"),
        _record(FindingCategory.OWNERSHIP_BEHAVIOUR, FindingTag.RESOLVED_CLEAN, "MCA"),
    ]

    result = score_vendor(vendor_id="vendor-under-test", records=records)

    assert result.score == 100.0
    assert result.recommendation == RecommendedAction.PROCEED


def test_duplicate_records_dont_produce_duplicate_reasons():
    # When the same OpenSanctions hit comes in twice (e.g., once via
    # key_persons screening and once via UBO lock), scoring should
    # collapse them so the "Why this score" trace isn't polluted.
    def _sanctions_red(ref: str = "sanctioned-id"):
        return EvidenceRecord(
            vendor_id="v1",
            category=FindingCategory.GLOBAL_COMPLIANCE,
            source_name="OpenSanctions",
            source_reference=ref,
            summary="Matched 'Mehul C. Choksi' in in_nse_debarred.",
            tag=FindingTag.RESOLVED_RED_FLAG,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.SUCCESS,
            citation_url="https://www.opensanctions.org/entities/sanctioned-id/",
        )

    result = score_vendor(vendor_id="v1", records=[_sanctions_red(), _sanctions_red()])
    assert result.recommendation == RecommendedAction.DECLINE
    assert len(result.reasons) == 1  # dedup'd, not 2 identical lines
