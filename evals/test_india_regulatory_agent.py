"""
Seam under test: screen_india_regulatory(vendor) — Day 1 stub for the
India regulatory category. GST, EPFO, and Udyam have no automated path in
this PoC (no GSP relationship, no free public API), so instead of
returning nothing this agent hands back a manual-checklist task per check
telling the analyst what to pull and where. RBI/CIBIL and SFIO are handled
elsewhere (CIBIL is vendor-declared; SFIO isn't part of this stub's scope).
"""
from decimal import Decimal

from agents.india_regulatory import screen_india_regulatory
from schemas.report import CanonicalCheck
from schemas.vendor import EntityType, VendorIntake

VENDOR = VendorIntake(
    vendor_id="vendor-a-suresh-enterprises",
    name="Suresh Enterprises",
    pan="AMMPK4657M",
    entity_type=EntityType.SOLE_PROPRIETORSHIP,
    contract_value=Decimal("500000"),
    has_physical_premises=False,
)


def test_emits_one_manual_checklist_task_each_for_gst_epfo_and_udyam():
    tasks = screen_india_regulatory(vendor=VENDOR)

    checks = {task.check for task in tasks}
    assert checks == {CanonicalCheck.GST, CanonicalCheck.EPFO, CanonicalCheck.MSME_UDYAM}
