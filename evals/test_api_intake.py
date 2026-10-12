"""
Seam under test: POST /vendors — the intake endpoint. Given a VendorIntake
payload, it should store the vendor and return the routed check fields
(orchestrator.route_checks) so the frontend can render the applicability
screen before the analyst deselects anything or the pipeline runs.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _vendor_payload(**overrides):
    payload = {
        "vendor_id": "vendor-a-suresh-enterprises",
        "name": "Suresh Enterprises",
        "pan": "AMMPK4657M",
        "entity_type": "sole_proprietorship",
        "contract_value": "500000",
        "has_physical_premises": False,
    }
    payload.update(overrides)
    return payload


def test_intake_returns_routed_fields_for_a_sole_proprietorship():
    response = client.post("/vendors", json=_vendor_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["vendor_id"] == "vendor-a-suresh-enterprises"

    fields_by_check = {f["check"]: f for f in body["fields"]}
    assert fields_by_check["mca"]["applicable"] is False
    assert fields_by_check["gst"]["applicable"] is True
    assert fields_by_check["pan_verification"]["applicable"] is True
    assert all(f["selected"] is True for f in body["fields"])
    assert all(f["color"] == "grey" for f in body["fields"])


def test_intake_rejects_a_malformed_pan():
    response = client.post("/vendors", json=_vendor_payload(pan="not-a-pan"))

    assert response.status_code == 422
