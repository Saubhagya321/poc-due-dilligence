"""
Seam under test: screen_litigation(vendor, indian_kanoon_api_key) — turns
the raw case docs from ecourts_case_search into a litigation finding.

Per the plan: 3+ same-counterparty NI Act 138 cases is a pattern of
cheque dishonour (a real, repeated payment-default signal, not a one-off),
while a single case is a milder signal that could be a one-time dispute.
Neither can be auto-confirmed as genuinely this vendor from a case title
alone (no PAN in judgments), so both stay `unresolved` and route to a
human — the pattern case just says so more forcefully in its summary so
the analyst knows to prioritise checking it.
"""
from schemas.evidence import CheckStatus, FindingCategory, FindingTag
from schemas.vendor import EntityType, VendorIntake
from decimal import Decimal

from agents.litigation import screen_litigation

VENDOR = VendorIntake(
    vendor_id="vendor-b-patel-and-sons",
    name="Patel and Sons",
    pan="AAAFP1234C",
    entity_type=EntityType.PARTNERSHIP,
    contract_value=Decimal("750000"),
    has_physical_premises=True,
)

_DOC = {
    "tid": 12345,
    "title": "Someone vs Patel and Sons on 1 January, 2024",
    "docsource": "Bangalore District Court",
}


def test_search_runs_multiple_query_variants_and_dedupes_by_tid(mocker):
    # Fraud / NCLT / money-laundering coverage can't be gotten from the NI
    # Act 138 query alone — SFIO/IBC chatter uses different wording. Fire
    # multiple topic queries and merge the results.
    from tools.indian_kanoon import ecourts_case_search

    captured_queries = []

    def fake_search(query, api_key):
        captured_queries.append(query)
        # Return overlapping tids across queries to prove dedupe works
        return {"docs": [
            {"tid": 1, "title": "A vs Patel and Sons", "docsource": "Court 1"},
            {"tid": 2, "title": "B vs Patel and Sons", "docsource": "Court 2"},
        ]}

    mocker.patch("tools.indian_kanoon._search", side_effect=fake_search)

    docs = ecourts_case_search(name="Patel and Sons", api_key="fake-key")

    # Multiple query variants fired
    assert len(captured_queries) >= 2
    joined = " | ".join(captured_queries).lower()
    assert any(kw in joined for kw in ("fraud", "money laundering", "insolvency", "nclt"))
    # Dedupe: 2 unique tids across all queries, not 2*N duplicates
    tids = [d["tid"] for d in docs]
    assert tids.count(1) == 1
    assert tids.count(2) == 1


def test_no_cases_found_is_confirmed_by_absence(mocker):
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[])

    records = screen_litigation(vendor=VENDOR, indian_kanoon_api_key="fake-key")

    assert len(records) == 1
    assert records[0].category == FindingCategory.LITIGATION
    assert records[0].tag == FindingTag.CONFIRMED_BY_ABSENCE
    assert records[0].check_status == CheckStatus.SUCCESS


def test_a_single_case_is_an_isolated_unresolved_finding(mocker):
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[_DOC])

    records = screen_litigation(vendor=VENDOR, indian_kanoon_api_key="fake-key")

    assert records[0].tag == FindingTag.UNRESOLVED
    assert records[0].check_status == CheckStatus.AMBIGUOUS_MATCH
    assert "isolated" in records[0].summary.lower()
    assert records[0].citation_url == "https://indiankanoon.org/doc/12345/"


def test_every_matching_case_is_exposed_as_a_supporting_citation_for_the_analyst_to_review(mocker):
    # The agent used to throw away every doc except docs[0]. For a common
    # name like "Patel and Sons", half of those discarded docs could be
    # about different same-named parties — the analyst needs to see each
    # one with its own citation URL to decide which (if any) actually
    # concern this vendor. Without this, the amber tile shows one case
    # when the API returned five.
    docs = [
        {"tid": 111, "title": "A vs Patel and Sons on 1 Jan 2024", "docsource": "Court 1"},
        {"tid": 222, "title": "B vs Patel and Sons on 2 Feb 2024", "docsource": "Court 2"},
        {"tid": 333, "title": "C vs Patel and Sons on 3 Mar 2024", "docsource": "Court 3"},
    ]
    mocker.patch("agents.litigation.ecourts_case_search", return_value=docs)

    records = screen_litigation(vendor=VENDOR, indian_kanoon_api_key="fake-key")

    citations = records[0].supporting_citations
    assert len(citations) == 3
    assert citations[0].url == "https://indiankanoon.org/doc/111/"
    assert citations[1].url == "https://indiankanoon.org/doc/222/"
    assert citations[2].url == "https://indiankanoon.org/doc/333/"
    assert citations[0].title == "A vs Patel and Sons on 1 Jan 2024"
    assert citations[0].source == "Court 1"


def test_three_or_more_cases_is_flagged_as_a_pattern(mocker):
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[_DOC, _DOC, _DOC])

    records = screen_litigation(vendor=VENDOR, indian_kanoon_api_key="fake-key")

    assert records[0].tag == FindingTag.UNRESOLVED
    assert "pattern" in records[0].summary.lower()
    assert "3" in records[0].summary
