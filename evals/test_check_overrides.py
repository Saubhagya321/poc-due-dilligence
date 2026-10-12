"""
Seam under test: orchestrator.apply_overrides(fields, deselected_checks) —
the analyst, looking at the intake screen produced by route_checks, can
turn off any check before the pipeline runs (e.g. they already have a
recent CIBIL report and don't need us to re-pull it).

Turning a check off is independent of whether it was applicable: an
analyst can deselect an applicable check (skip it deliberately), but
cannot select a check that isn't applicable to this entity type in the
first place — there's nothing to run.
"""
from schemas.report import CanonicalCheck, CheckStatusColor
from schemas.vendor import EntityType
from orchestrator.orchestrator import apply_overrides, route_checks


def test_deselecting_an_applicable_check_turns_off_selected_but_leaves_it_applicable():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)

    updated = apply_overrides(fields, deselected_checks=[CanonicalCheck.RBI_CIBIL])

    rbi = next(f for f in updated if f.check == CanonicalCheck.RBI_CIBIL)
    assert rbi.selected is False
    assert rbi.applicable is True
    assert rbi.color == CheckStatusColor.GREY


def test_deselecting_a_check_that_is_not_applicable_is_a_no_op():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)

    updated = apply_overrides(fields, deselected_checks=[CanonicalCheck.SEBI])

    sebi = next(f for f in updated if f.check == CanonicalCheck.SEBI)
    assert sebi.applicable is False
    assert sebi.selected is False


def test_checks_not_named_in_the_override_stay_selected():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)

    updated = apply_overrides(fields, deselected_checks=[CanonicalCheck.RBI_CIBIL])

    gst = next(f for f in updated if f.check == CanonicalCheck.GST)
    assert gst.selected is True
