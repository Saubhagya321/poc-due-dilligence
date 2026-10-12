"""
Seam under test: adverse_media_search(vendor_id, name, api_key) — the public
entry point agents call to check open-web news for fraud/bribery mentions.

We mock the low-level HTTP call (_search). The fixtures are real Tavily
responses captured live:

- tavily_nirav_modi_adverse_media.json: searching a real fraud case returns
  5 genuinely relevant results, all scored 0.68-0.89.
- tavily_suresh_enterprises_no_adverse_media.json: searching our fictional
  clean vendor's name returns 5 results too, but they're all irrelevant noise
  (a different "Suresh", a different "Enterprises", generic scam news) scored
  only 0.05-0.33.

Unlike OpenSanctions, Tavily has no identity resolution — it's just text
relevance ranking, so it can't confirm an article is actually about this
vendor and not a same-named, unrelated one. We proved this live: searching
the literal name "Suresh Enterprises" surfaced an unrelated Facebook
complaint about a same-named business, scored 0.572 — above what looked
like a safe threshold. So a relevant hit is never auto-flagged as a red
flag; it's marked unresolved so a human can confirm identity (e.g. against
the vendor's PAN via a registry lookup), which is also the only tag that
should ever come with a citation_url pointing at the specific article.
"""
import json
from pathlib import Path

from schemas.evidence import CheckStatus, FindingTag
from tools.tavily_search import adverse_media_search

FIXTURES = Path(__file__).parent / "fixtures"


def _load(filename: str) -> dict:
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


def test_high_relevance_results_are_unresolved_pending_human_identity_check(mocker):
    mocker.patch(
        "tools.tavily_search._search",
        return_value=_load("tavily_nirav_modi_adverse_media.json"),
    )

    record = adverse_media_search(
        vendor_id="vendor-x-nirav-modi-test",
        name="Nirav Modi",
        api_key="fake-key",
    )

    assert record.tag == FindingTag.UNRESOLVED
    assert record.check_status == CheckStatus.AMBIGUOUS_MATCH
    assert record.citation_url == "https://en.wikipedia.org/wiki/Nirav_Modi"


def test_low_relevance_noise_is_confirmed_by_absence(mocker):
    mocker.patch(
        "tools.tavily_search._search",
        return_value=_load("tavily_suresh_enterprises_no_adverse_media.json"),
    )

    record = adverse_media_search(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Enterprises",
        api_key="fake-key",
    )

    assert record.tag == FindingTag.CONFIRMED_BY_ABSENCE
    assert record.check_status == CheckStatus.SUCCESS


def test_no_results_at_all_is_confirmed_by_absence(mocker):
    mocker.patch(
        "tools.tavily_search._search",
        return_value={"results": []},
    )

    record = adverse_media_search(
        vendor_id="vendor-a-suresh-enterprises",
        name="Some Other Clean Name",
        api_key="fake-key",
    )

    assert record.tag == FindingTag.CONFIRMED_BY_ABSENCE
    assert record.check_status == CheckStatus.SUCCESS
