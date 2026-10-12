"""
Seam under test: ecourts_case_search(name, api_key) — searches Indian
Kanoon (case law + judgments) for cheque-bounce (NI Act 138) cases and
returns the docs whose title actually names the vendor.

We mock the low-level HTTP call (_search), not the filtering logic. The
fixture (indiankanoon_cheque_bounce_search.json) is a real captured
response for the generic query "cheque bounce NI Act 138" — it has 10
unrelated cases from different parties, so filtering by name is what turns
a generic docket dump into vendor-specific hits. Two of its docs have
"Suresh.S" and "Suresh Enterprises" style names we use to test the filter.
"""
import json
from pathlib import Path

from tools.indian_kanoon import ecourts_case_search

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture() -> dict:
    return json.loads(
        (FIXTURES / "indiankanoon_cheque_bounce_search.json").read_text(encoding="utf-8")
    )


def test_only_docs_whose_title_names_the_vendor_are_returned(mocker):
    mocker.patch("tools.indian_kanoon._search", return_value=_load_fixture())

    docs = ecourts_case_search(name="Suresh.S", api_key="fake-key")

    assert len(docs) == 1
    assert docs[0]["title"] == "Y Krishnamurthy vs Suresh.S on 15 April, 2024"


def test_no_matching_docs_returns_an_empty_list(mocker):
    mocker.patch("tools.indian_kanoon._search", return_value=_load_fixture())

    docs = ecourts_case_search(name="A Name Nobody In These Cases Has", api_key="fake-key")

    assert docs == []
