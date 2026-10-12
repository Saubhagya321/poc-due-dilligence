"""
Seam under test: run_vendor_screening(vendor, ...) — the full pipeline for
one vendor.

Per the plan's verification checklist ("Vendor A workflow test passes
end-to-end with a real OpenSanctions call"), OpenSanctions stays live here.
Tavily and Indian Kanoon are mocked instead: we found live Tavily
results/scores are non-deterministic between identical calls (same query,
different top hit and score each time), which would make this test flaky
for reasons unrelated to our code. Indian Kanoon is mocked for the same
reason — a live case search could surface an unrelated same-named
defendant and turn a "clean" fixture into a flaky failure.

Vendor A ("Suresh Enterprises", sole proprietorship) is the plan's clean
example: no sanctions hit, no adverse media, no litigation hits -> should
proceed. Only global compliance + litigation run on Day 1, so this
vendor's score is judged across the categories actually checked, not a
hardcoded 4.

Vendor B ("Patel and Sons", partnership) exercises the litigation
pattern-detection path: 3 same-named cheque-bounce cases route to
`unresolved` (not an auto red-flag — a case title alone can't be confirmed
as genuinely this vendor without a human checking it against the PAN, same
principle as the OpenSanctions/Tavily identity-ambiguity handling), which
drags the score below the proceed threshold. OpenSanctions is mocked clean
here (live-tested once, live and found "Patel and Sons" pulls back an
unrelated tied match — the same common-name false-positive problem as
"Suresh Kumar" — which isn't what this test is about; that identity
ambiguity is already covered by the OpenSanctions tool's own tests).
"""
from decimal import Decimal

import pytest

from schemas.vendor import EntityType, VendorIntake
from schemas.report import RecommendedAction
from workflows.vendor_screening import run_vendor_screening


def _load_env(path: str = ".env") -> dict:
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env


ENV = _load_env()


@pytest.mark.skipif(
    not ENV.get("OPENSANCTIONS_API"),
    reason="requires a real OPENSANCTIONS_API key in .env",
)
def test_vendor_a_runs_end_to_end_and_recommends_proceed(mocker):
    mocker.patch(
        "tools.tavily_search._search",
        return_value={
            "results": [
                {
                    "url": "https://www.facebook.com/groups/444293060184156/posts/1443011536978965",
                    "title": "Scammed by Suresh Enterprises for airline calls",
                    "content": "unrelated noise, low relevance",
                    "score": 0.33,
                }
            ]
        },
    )
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[])

    vendor = VendorIntake(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Enterprises",
        pan="AMMPK4657M",
        entity_type=EntityType.SOLE_PROPRIETORSHIP,
        contract_value=Decimal("500000"),
        has_physical_premises=False,
    )

    result = run_vendor_screening(
        vendor=vendor,
        opensanctions_api_key=ENV["OPENSANCTIONS_API"],
        tavily_api_key="unused-because-tavily-is-mocked",
        indian_kanoon_api_key="unused-because-indian-kanoon-is-mocked",
    )

    assert result.recommendation == RecommendedAction.PROCEED


def test_vendor_b_has_a_litigation_pattern_and_does_not_proceed_cleanly(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value={"results": [], "total": {"value": 0, "relation": "eq"}},
    )
    mocker.patch(
        "tools.tavily_search._search",
        return_value={"results": []},
    )
    case_doc = {
        "tid": 55555,
        "title": "Supplier X vs Patel and Sons on 1 January, 2024",
        "docsource": "Delhi District Court",
    }
    mocker.patch(
        "agents.litigation.ecourts_case_search",
        return_value=[case_doc, case_doc, case_doc],
    )

    vendor = VendorIntake(
        vendor_id="vendor-b-patel-and-sons",
        name="Patel and Sons",
        pan="AAAFP1234C",
        entity_type=EntityType.PARTNERSHIP,
        contract_value=Decimal("750000"),
        has_physical_premises=True,
    )

    result = run_vendor_screening(
        vendor=vendor,
        opensanctions_api_key="unused-because-opensanctions-is-mocked",
        tavily_api_key="unused-because-tavily-is-mocked",
        indian_kanoon_api_key="unused-because-indian-kanoon-is-mocked",
    )

    assert result.recommendation != RecommendedAction.PROCEED
    assert any("pattern" in reason.lower() for reason in result.reasons)


# Vendor C ("Meridian Components with Singapore parent") used to be a
# dedicated workflow test for the intake-driven foreign-UBO stub. That
# stub was retired when UBO moved to a dedicated analyst-driven tile
# (UBO panel: upload MGT-7 -> extract graph -> lock), covered by its own
# endpoint tests. Nothing left to test at the workflow level for this case.
