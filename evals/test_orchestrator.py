"""
Seam under test: plan_checks(entity_type) — decides which checks apply to a
vendor before any agent runs.

Sole proprietorships, partnerships, and HUFs aren't registered with the MCA
(India's registrar of companies) — there's no corporate filing to check, so
that check is skipped rather than run and come back empty every time.
LLPs and companies are registered, so the check applies.
"""
from orchestrator.orchestrator import plan_checks
from schemas.vendor import EntityType


def test_sole_proprietorship_excludes_the_mca_sebi_check():
    checks = plan_checks(EntityType.SOLE_PROPRIETORSHIP)

    assert "mca_sebi_nse_bse" not in checks


def test_private_limited_includes_the_mca_sebi_check():
    checks = plan_checks(EntityType.PRIVATE_LIMITED)

    assert "mca_sebi_nse_bse" in checks
    assert "global_compliance" in checks
