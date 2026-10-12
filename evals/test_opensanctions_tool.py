"""
Seam under test: sanctions_pep_screen(vendor_id, name, pan, api_key) — the
public entry point agents call to screen a vendor/person name against
OpenSanctions.

We mock the low-level HTTP call (_search) here, not the classification logic.
The fixtures below are real API responses captured live:

- opensanctions_putin_match.json: a clean single hit (1 result, unambiguous)
  should become a resolved-red-flag.
- opensanctions_suresh_kumar_ambiguous_common_name.json: a real false-positive
  we discovered — 3 different entity IDs tied at the top score of 1.0 for a
  common Indian name. One of them (an NSE-debarred "Suresh Kumar") carries a
  taxNumber ("AMMPK4657M") in the real data. If that matches the vendor's own
  PAN, we know it's genuinely them — resolve to a red flag on that specific
  entity. If the vendor's PAN matches none of the tied candidates, we still
  can't tell them apart, so it stays ambiguous and routes to a human.
"""
import json
from pathlib import Path

from schemas.evidence import CheckStatus, FindingTag
from tools.opensanctions import sanctions_pep_screen

FIXTURES = Path(__file__).parent / "fixtures"


def _load_q1(filename: str) -> dict:
    data = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    return data["responses"]["q1"]


def test_a_single_unambiguous_hit_is_a_resolved_red_flag(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value=_load_q1("opensanctions_putin_match.json"),
    )

    record = sanctions_pep_screen(
        vendor_id="vendor-b-patel-and-sons",
        name="Vladimir Putin",
        pan="AAAAA1111A",
        api_key="fake-key",
    )

    assert record.tag == FindingTag.RESOLVED_RED_FLAG
    assert record.check_status == CheckStatus.SUCCESS
    assert record.source_reference == "Q7747"


def test_tied_top_scores_with_no_pan_match_routes_to_a_human(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value=_load_q1("opensanctions_suresh_kumar_ambiguous_common_name.json"),
    )

    record = sanctions_pep_screen(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Kumar",
        pan="ZZZZZ9999Z",
        api_key="fake-key",
    )

    assert record.tag == FindingTag.UNRESOLVED
    assert record.check_status == CheckStatus.AMBIGUOUS_MATCH


def test_tied_top_scores_resolved_by_a_matching_pan_becomes_a_red_flag(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value=_load_q1("opensanctions_suresh_kumar_ambiguous_common_name.json"),
    )

    record = sanctions_pep_screen(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Kumar",
        pan="AMMPK4657M",  # matches the NSE-debarred candidate's real taxNumber
        api_key="fake-key",
    )

    assert record.tag == FindingTag.RESOLVED_RED_FLAG
    assert record.check_status == CheckStatus.SUCCESS
    assert record.source_reference == "in-nse-deb-acf9e8b7892a812ea6de2be78073fb5de2a0aa30"


def test_no_results_is_resolved_clean(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value={"results": [], "total": {"value": 0, "relation": "eq"}},
    )

    record = sanctions_pep_screen(
        vendor_id="vendor-a-suresh-enterprises",
        name="Some Clean Name",
        pan="AAAAA1111A",
        api_key="fake-key",
    )

    assert record.tag == FindingTag.RESOLVED_CLEAN
    assert record.check_status == CheckStatus.SUCCESS


def test_fuzzy_matches_not_containing_vendor_tokens_are_rejected(mocker):
    # Live-captured bug: screening "Q3 InfoTech Pvt. Ltd." against OpenSanctions
    # returned 3 unrelated entities tied at 0.75 — Ecospace Infotech, KPT Infotech,
    # Goglet Infotech — all on India's NSE debarred list but NONE of them Q3.
    # The old pipeline flagged this as UNRESOLVED (amber) because the IDs
    # differed. The anchor-token filter rejects any hit whose caption lacks
    # the vendor's distinctive first token ("q3"), so this becomes a clean
    # no-match instead of a false amber.
    fake_response = {
        "results": [
            {"id": "x1", "score": 0.75, "caption": "Ecospace Infotech Pvt. Ltd.",
             "properties": {"topics": ["reg.warn"]}, "datasets": ["in_nse_debarred"]},
            {"id": "x2", "score": 0.75, "caption": "KPT Infotech Pvt. Ltd.",
             "properties": {"topics": ["reg.warn"]}, "datasets": ["in_nse_debarred"]},
            {"id": "x3", "score": 0.75, "caption": "Goglet Infotech Pvt. Ltd.",
             "properties": {"topics": ["reg.warn"]}, "datasets": ["in_nse_debarred"]},
        ]
    }
    mocker.patch("tools.opensanctions._search", return_value=fake_response)

    from tools.opensanctions import sanctions_pep_screen
    from schemas.evidence import FindingTag

    record = sanctions_pep_screen(
        vendor_id="v-q3", name="Q3 InfoTech Pvt. Ltd.", pan=None, api_key="fake-key"
    )

    assert record.tag == FindingTag.RESOLVED_CLEAN
    assert record.source_reference == "no-match"


def test_fuzzy_matches_containing_vendor_tokens_still_flag_correctly(mocker):
    # Guardrail test: the anchor filter must NOT accidentally drop legitimate
    # hits. If the matched entity caption DOES contain the vendor's distinctive
    # tokens, it should still produce a red-flag record as before.
    fake_response = {
        "results": [
            {"id": "real-match", "score": 0.92, "caption": "Mehul C. Choksi",
             "properties": {"topics": ["debarment", "reg.warn"], "sourceUrl": ["https://x"]},
             "datasets": ["in_nse_debarred"]},
        ]
    }
    mocker.patch("tools.opensanctions._search", return_value=fake_response)

    from tools.opensanctions import sanctions_pep_screen
    from schemas.evidence import FindingTag

    record = sanctions_pep_screen(
        vendor_id="v-choksi", name="Mehul Choksi", pan=None, api_key="fake-key"
    )

    assert record.tag == FindingTag.RESOLVED_RED_FLAG
