"""
Unit tests for the four eKYC-backed agents (MCA/CIN, GST, Udyam, PAN).

We mock the low-level eKYC tool calls, not the agent classification logic —
same pattern as the OpenSanctions/Indian Kanoon agent tests. Fixtures below
mirror the shapes documented in Message Central's own docs page.
"""
from decimal import Decimal

from schemas.evidence import FindingTag
from schemas.vendor import EntityType, VendorIntake
from tools.ekyc import EkycError, EkycInvalidInput


def _vendor(**overrides):
    base = dict(
        vendor_id="v1",
        name="Acme Private Limited",
        pan="AAACA1234C",
        entity_type=EntityType.PRIVATE_LIMITED,
        contract_value=Decimal("10000000"),
        has_physical_premises=True,
    )
    base.update(overrides)
    return VendorIntake(**base)


# --- MCA / CIN agent ---------------------------------------------------------

def test_mca_active_cin_becomes_resolved_clean(mocker):
    from agents.mca_cin import screen_mca
    mocker.patch(
        "agents.mca_cin.verify_cin",
        return_value={
            "status": "VALID",
            "cin": "U72900KA2015PTC082988",
            "company_name": "Acme Private Limited",
            "cin_status": "ACTIVE",
            "incorporation_date": "2015-01-01",
        },
    )
    records = screen_mca(_vendor(cin="U72900KA2015PTC082988"), "k", "c")
    assert len(records) == 1
    assert records[0].tag == FindingTag.RESOLVED_CLEAN
    assert "ACTIVE" in records[0].summary


def test_mca_struck_off_becomes_red(mocker):
    from agents.mca_cin import screen_mca
    mocker.patch(
        "agents.mca_cin.verify_cin",
        return_value={"cin_status": "STRIKE OFF", "cin": "X", "company_name": "Acme"},
    )
    records = screen_mca(_vendor(cin="U72900KA2015PTC082988"), "k", "c")
    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG
    assert "STRIKE OFF" in records[0].summary


def test_mca_no_cin_supplied_produces_no_record(mocker):
    from agents.mca_cin import screen_mca
    records = screen_mca(_vendor(cin=None), "k", "c")
    assert records == []


def test_mca_not_applicable_for_sole_prop(mocker):
    from agents.mca_cin import screen_mca
    records = screen_mca(
        _vendor(entity_type=EntityType.SOLE_PROPRIETORSHIP, pan="AMMPK4657M", cin="X"),
        "k", "c",
    )
    assert records == []


def test_mca_tech_failure_becomes_unresolved(mocker):
    from agents.mca_cin import screen_mca
    mocker.patch("agents.mca_cin.verify_cin", side_effect=EkycError("Network error"))
    records = screen_mca(_vendor(cin="U72900KA2015PTC082988"), "k", "c")
    assert records[0].tag == FindingTag.UNRESOLVED


def test_mca_invalid_cin_becomes_unresolved(mocker):
    from agents.mca_cin import screen_mca
    mocker.patch(
        "agents.mca_cin.verify_cin",
        side_effect=EkycInvalidInput("cin_value_invalid"),
    )
    records = screen_mca(_vendor(cin="BADCIN"), "k", "c")
    assert records[0].tag == FindingTag.UNRESOLVED


# --- GST agent ---------------------------------------------------------------

def test_gst_all_active_gstins_becomes_clean(mocker):
    from agents.gst_registry import screen_gst
    mocker.patch(
        "agents.gst_registry.fetch_gstin_with_pan",
        return_value={
            "status": "SUCCESS", "pan": "AAACA1234C",
            "gstin_list": [{"gstin": "27AAACA1234C1Z5", "status": "Active", "state": "MH"}],
        },
    )
    mocker.patch(
        "agents.gst_registry.verify_gstin",
        return_value={
            "GSTIN": "27AAACA1234C1Z5",
            "legal_name_of_business": "Acme Private Limited",
            "gst_in_status": "Active",
        },
    )
    records = screen_gst(_vendor(), "k", "c")
    assert records[0].tag == FindingTag.RESOLVED_CLEAN
    assert "Active" in records[0].summary


def test_gst_cancelled_gstin_becomes_red(mocker):
    from agents.gst_registry import screen_gst
    mocker.patch(
        "agents.gst_registry.fetch_gstin_with_pan",
        return_value={"gstin_list": [{"gstin": "27AAACA1234C1Z5"}]},
    )
    mocker.patch(
        "agents.gst_registry.verify_gstin",
        return_value={
            "GSTIN": "27AAACA1234C1Z5",
            "legal_name_of_business": "Acme Private Limited",
            "gst_in_status": "Cancelled",
        },
    )
    records = screen_gst(_vendor(), "k", "c")
    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG


def test_gst_empty_gstin_list_becomes_unresolved(mocker):
    from agents.gst_registry import screen_gst
    mocker.patch(
        "agents.gst_registry.fetch_gstin_with_pan",
        return_value={"gstin_list": []},
    )
    records = screen_gst(_vendor(), "k", "c")
    assert records[0].tag == FindingTag.UNRESOLVED


def test_gst_mixed_statuses_become_unresolved(mocker):
    from agents.gst_registry import screen_gst
    mocker.patch(
        "agents.gst_registry.fetch_gstin_with_pan",
        return_value={
            "gstin_list": [{"gstin": "27AAACA1234C1Z5"}, {"gstin": "29AAACA1234C1Z5"}],
        },
    )
    responses = iter([
        {"GSTIN": "27AAACA1234C1Z5", "gst_in_status": "Active"},
        {"GSTIN": "29AAACA1234C1Z5", "gst_in_status": "Suspended"},  # cancelled -> red hits
    ])
    mocker.patch("agents.gst_registry.verify_gstin", side_effect=lambda *a, **kw: next(responses))
    records = screen_gst(_vendor(), "k", "c")
    # Suspended counts as a red-status match
    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG


def test_gst_not_applicable_for_foreign_entity(mocker):
    from agents.gst_registry import screen_gst
    records = screen_gst(
        _vendor(entity_type=EntityType.FOREIGN_ENTITY, pan=None, cin=None), "k", "c",
    )
    assert records == []


# --- Udyam agent -------------------------------------------------------------

def test_udyam_active_micro_enterprise_becomes_clean(mocker):
    from agents.udyam_registry import screen_udyam
    mocker.patch(
        "agents.udyam_registry.verify_udyam",
        return_value={
            "status": "SUCCESS",
            "udyam_number": "UDYAM-MH-01-0000001",
            "enterprise_name": "Acme Private Limited",
            "enterprise_type": "Micro",
        },
    )
    records = screen_udyam(_vendor(udyam_number="UDYAM-MH-01-0000001"), "k", "c")
    assert records[0].tag == FindingTag.RESOLVED_CLEAN
    assert "Micro" in records[0].summary


def test_udyam_not_found_becomes_red(mocker):
    from agents.udyam_registry import screen_udyam
    mocker.patch(
        "agents.udyam_registry.verify_udyam",
        return_value={"status": "NOT_FOUND", "udyam_number": "UDYAM-MH-01-9999999"},
    )
    records = screen_udyam(_vendor(udyam_number="UDYAM-MH-01-9999999"), "k", "c")
    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG


def test_udyam_no_number_supplied_produces_no_record(mocker):
    from agents.udyam_registry import screen_udyam
    records = screen_udyam(_vendor(udyam_number=None), "k", "c")
    assert records == []


# --- PAN upgrade (entity_resolution) ----------------------------------------

def test_pan_falls_back_to_format_check_when_no_ekyc_creds(mocker):
    from agents.entity_resolution import screen_entity_resolution
    records = screen_entity_resolution(_vendor(), ekyc_api_key="", ekyc_customer_id="")
    assert records[0].source_name == "PAN format check"
    assert records[0].tag == FindingTag.RESOLVED_CLEAN


def test_pan_valid_with_name_match_becomes_clean(mocker):
    from agents.entity_resolution import screen_entity_resolution
    mocker.patch(
        "agents.entity_resolution.verify_pan_sync",
        return_value={
            "pan": "AAACA1234C",
            "valid": True,
            "pan_status": "VALID",
            "name_pan_card": "Acme Private Limited",
            "name_match_result": "Y",
            "name_match_score": 95,
        },
    )
    records = screen_entity_resolution(_vendor(), ekyc_api_key="k", ekyc_customer_id="c")
    assert records[0].source_name == "eKYC Now (PAN)"
    assert records[0].tag == FindingTag.RESOLVED_CLEAN


def test_pan_valid_but_name_mismatch_becomes_unresolved(mocker):
    from agents.entity_resolution import screen_entity_resolution
    mocker.patch(
        "agents.entity_resolution.verify_pan_sync",
        return_value={
            "pan": "AAACA1234C",
            "valid": True,
            "pan_status": "VALID",
            "name_pan_card": "Totally Different Industries",
            "name_match_result": "N",
            "name_match_score": 20,
        },
    )
    records = screen_entity_resolution(_vendor(), ekyc_api_key="k", ekyc_customer_id="c")
    assert records[0].tag == FindingTag.UNRESOLVED


def test_pan_rejected_by_nsdl_becomes_red(mocker):
    from agents.entity_resolution import screen_entity_resolution
    mocker.patch(
        "agents.entity_resolution.verify_pan_sync",
        side_effect=EkycInvalidInput("pan_value_invalid: not a valid PAN"),
    )
    records = screen_entity_resolution(_vendor(), ekyc_api_key="k", ekyc_customer_id="c")
    assert records[0].tag == FindingTag.RESOLVED_RED_FLAG


def test_pan_tech_failure_falls_back_gracefully(mocker):
    from agents.entity_resolution import screen_entity_resolution
    mocker.patch(
        "agents.entity_resolution.verify_pan_sync",
        side_effect=EkycError("Network error"),
    )
    records = screen_entity_resolution(_vendor(), ekyc_api_key="k", ekyc_customer_id="c")
    assert records[0].tag == FindingTag.UNRESOLVED
