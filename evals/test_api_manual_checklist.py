"""
Seam under test: GET /vendors/{vendor_id}/manual-checklist — surfaces the
guided-checklist tasks (tools.manual_checklist.build_manual_checklist) for
whichever selected+applicable checks have no automated path, using the
vendor's current routed fields (post-overrides).
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_manual_checklist_lists_only_selected_applicable_manual_checks():
    client.post(
        "/vendors",
        json={
            "vendor_id": "vendor-a-suresh-enterprises",
            "name": "Suresh Enterprises",
            "pan": "AMMPK4657M",
            "entity_type": "sole_proprietorship",
            "contract_value": "500000",
            "has_physical_premises": False,
        },
    )

    response = client.get("/vendors/vendor-a-suresh-enterprises/manual-checklist")

    assert response.status_code == 200
    checks = {task["check"] for task in response.json()}
    assert "gst" in checks
    assert "mca" not in checks  # sole proprietorship: MCA not applicable
    assert "sanctions_pep" not in checks  # automated, not a manual-checklist item


def test_manual_checklist_for_an_unknown_vendor_returns_404():
    response = client.get("/vendors/does-not-exist/manual-checklist")

    assert response.status_code == 404
