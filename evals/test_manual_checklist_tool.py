"""
Seam under test: build_manual_checklist(checks) — for the checks the plan
never automates (GST, EPFO, Udyam, RBI/CIBIL, SFIO — no self-serve API,
no GSP relationship, structurally restricted), emit a structured task
telling the analyst what to fetch and where, instead of silently doing
nothing. Each task names the check, gives plain-language instructions, and
a portal hint (where to go look).

A check with no known manual instruction (e.g. one of the automated ones)
is simply skipped — this tool only emits tasks for the checks it knows
about, it doesn't fabricate placeholder instructions for the rest.
"""
from schemas.report import CanonicalCheck
from tools.manual_checklist import build_manual_checklist


def test_gst_and_cibil_each_produce_a_task_naming_their_check():
    tasks = build_manual_checklist([CanonicalCheck.GST, CanonicalCheck.RBI_CIBIL])

    checks = {task.check for task in tasks}
    assert checks == {CanonicalCheck.GST, CanonicalCheck.RBI_CIBIL}
    for task in tasks:
        assert task.instruction
        assert task.portal_hint


def test_a_check_with_no_manual_instruction_is_skipped_not_fabricated():
    tasks = build_manual_checklist([CanonicalCheck.SANCTIONS_PEP])

    assert tasks == []


def test_an_unselected_check_produces_no_task_even_if_it_has_an_instruction():
    tasks = build_manual_checklist([])

    assert tasks == []


def test_mca_nse_bse_nclt_route_to_manual_single_company_lookup_portals():
    # data.gov.in's bulk dataset (the planned MCA ingest source) is under
    # maintenance. Each of these checks has its own free, live,
    # single-company lookup portal that doesn't depend on that bulk
    # dataset, so they're manual-checklist items instead of blocked fetches.
    tasks = build_manual_checklist(
        [CanonicalCheck.MCA, CanonicalCheck.NSE, CanonicalCheck.BSE, CanonicalCheck.NCLT]
    )

    checks = {task.check for task in tasks}
    assert checks == {
        CanonicalCheck.MCA,
        CanonicalCheck.NSE,
        CanonicalCheck.BSE,
        CanonicalCheck.NCLT,
    }
    for task in tasks:
        assert task.instruction
        assert task.portal_hint
