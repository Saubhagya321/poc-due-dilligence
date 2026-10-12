"""
Seam under test: POST /vendors/{vendor_id}/run — runs the full pipeline
against a previously intaken (and possibly overridden) vendor and returns
the colour-coded Report. Tavily/OpenSanctions/Indian Kanoon are mocked for
the same non-determinism reasons as workflows/vendor_screening.py's own
tests — this test is about the endpoint wiring, not agent behaviour.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _intake(vendor_id="vendor-a-suresh-enterprises"):
    return client.post(
        "/vendors",
        json={
            "vendor_id": vendor_id,
            "name": "Suresh Enterprises",
            "pan": "AMMPK4657M",
            "entity_type": "sole_proprietorship",
            "contract_value": "500000",
            "has_physical_premises": False,
        },
    )


def test_run_returns_a_report_for_a_previously_intaken_vendor(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value={"results": [], "total": {"value": 0, "relation": "eq"}},
    )
    mocker.patch("tools.tavily_search._search", return_value={"results": []})
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[])
    # eKYC credentials may be present in .env — null them for this endpoint
    # test so it stays focused on wiring. The eKYC agents have their own
    # mocked tests; mixing live network calls into this one makes it flaky.
    mocker.patch("api.main.EKYC_API_KEY", "")
    mocker.patch("api.main.EKYC_CUSTOMER_ID", "")
    _intake()

    response = client.post("/vendors/vendor-a-suresh-enterprises/run")

    assert response.status_code == 200
    body = response.json()
    assert body["vendor_id"] == "vendor-a-suresh-enterprises"
    assert body["recommendation"] == "proceed"
    fields_by_check = {f["check"]: f for f in body["fields"]}
    assert fields_by_check["pan_verification"]["color"] == "green"
    assert fields_by_check["sanctions_pep"]["color"] == "green"


def test_run_for_an_unknown_vendor_returns_404():
    response = client.post("/vendors/does-not-exist/run")

    assert response.status_code == 404
