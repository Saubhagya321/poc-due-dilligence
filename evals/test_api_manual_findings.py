"""
Seam under test: POST/GET /vendors/{vendor_id}/manual-findings — lets an
analyst submit what they found while working a manual-checklist item (see
/vendors/{id}/manual-checklist) and feeds it into the next /run the same
way an automated tool's finding would.
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


def test_submitting_a_manual_finding_returns_the_evidence_record():
    _intake("vendor-manual-1")

    response = client.post(
        "/vendors/vendor-manual-1/manual-findings",
        json={
            "check": "gst",
            "tag": "resolved-clean",
            "summary": "GSTIN Active, no defaults on record.",
            "citation_url": "https://services.gst.gov.in/services/searchtp",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tag"] == "resolved-clean"
    assert body["source_name"] == "Analyst manual entry"


def test_submitting_a_finding_for_an_automated_check_is_rejected():
    _intake("vendor-manual-2")

    response = client.post(
        "/vendors/vendor-manual-2/manual-findings",
        json={"check": "pan_verification", "tag": "resolved-clean", "summary": "Looks fine."},
    )

    assert response.status_code == 422


def test_manual_finding_feeds_into_the_report_after_run(mocker):
    mocker.patch(
        "tools.opensanctions._search",
        return_value={"results": [], "total": {"value": 0, "relation": "eq"}},
    )
    mocker.patch("tools.tavily_search._search", return_value={"results": []})
    mocker.patch("agents.litigation.ecourts_case_search", return_value=[])
    _intake("vendor-manual-3")
    client.post(
        "/vendors/vendor-manual-3/manual-findings",
        json={
            "check": "gst",
            "tag": "resolved-clean",
            "summary": "GSTIN Active, no defaults on record.",
            "citation_url": "https://services.gst.gov.in/services/searchtp",
        },
    )

    response = client.post("/vendors/vendor-manual-3/run")

    fields_by_check = {f["check"]: f for f in response.json()["fields"]}
    assert fields_by_check["gst"]["color"] == "green"
    assert fields_by_check["gst"]["source_name"] == "Analyst manual entry"


def test_resubmitting_the_same_check_overwrites_the_previous_finding():
    _intake("vendor-manual-4")
    client.post(
        "/vendors/vendor-manual-4/manual-findings",
        json={"check": "gst", "tag": "resolved-clean", "summary": "First look: fine."},
    )

    client.post(
        "/vendors/vendor-manual-4/manual-findings",
        json={
            "check": "gst",
            "tag": "resolved-red-flag",
            "summary": "Actually cancelled for non-filing.",
            "citation_url": "https://services.gst.gov.in/services/searchtp",
        },
    )

    findings = client.get("/vendors/vendor-manual-4/manual-findings").json()
    gst_findings = [f for f in findings if f["source_reference"] == "gst"]
    assert len(gst_findings) == 1
    assert gst_findings[0]["tag"] == "resolved-red-flag"


def test_manual_findings_for_an_unknown_vendor_returns_404():
    response = client.post(
        "/vendors/does-not-exist/manual-findings",
        json={"check": "gst", "tag": "resolved-clean", "summary": "n/a"},
    )

    assert response.status_code == 404
