from schemas.report import CanonicalCheck, ManualChecklistTask
from schemas.vendor import VendorIntake
from tools.manual_checklist import build_manual_checklist

STUB_CHECKS = [CanonicalCheck.GST, CanonicalCheck.EPFO, CanonicalCheck.MSME_UDYAM]


def screen_india_regulatory(vendor: VendorIntake) -> list[ManualChecklistTask]:
    """
    Day 1 stub: GST, EPFO, and Udyam have no automated path in this PoC, so
    this agent hands back a manual-checklist task per check instead of
    silently doing nothing.
    """
    return build_manual_checklist(STUB_CHECKS)
