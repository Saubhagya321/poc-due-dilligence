"""
Seam under test: PATCH /vendors/{vendor_id}/checks — the analyst's
deselect step between intake and running the pipeline
(orchestrator.apply_overrides). Only touches checks the analyst chose to
turn off; everything else stays as routed at intake.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _intake(vendor_id="vendor-a-suresh-enterprises"):
    client.post(
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


def test_deselecting_a_check_turns_it_grey_and_leaves_the_rest_untouched():
    _intake()

    response = client.patch(
        "/vendors/vendor-a-suresh-enterprises/checks",
        json={"deselected_checks": ["gst"]},
    )

    assert response.status_code == 200
    fields_by_check = {f["check"]: f for f in response.json()["fields"]}
    assert fields_by_check["gst"]["selected"] is False
    assert fields_by_check["pan_verification"]["selected"] is True


def test_overrides_for_an_unknown_vendor_returns_404():
    response = client.patch(
        "/vendors/does-not-exist/checks",
        json={"deselected_checks": ["gst"]},
    )

    assert response.status_code == 404
