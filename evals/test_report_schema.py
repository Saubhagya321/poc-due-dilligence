"""
Seam under test: schemas/report.py — the vocabulary for the final,
per-check report screen.

Per the user's request, the report must show one line per check (the 12
regulator/registry checks from the spec, plus global compliance as an
always-on 13th) with a colour:
  - green = resolved-clean / confirmed-by-absence (accepted)
  - red   = resolved-red-flag (rejected)
  - grey  = not selected by the analyst at intake (never ran)
  - amber = ran but came back unresolved / vendor-declared (needs a human,
            not yet accepted or rejected) — proposed in addition to the
            three colours the user named, since resolved-red-flag and
            unresolved are not the same thing and collapsing them into one
            colour would hide that distinction from the analyst.

Each field must carry either a citation (source + reference/url) when it
ran, or a reason when it was skipped/restricted, so the analyst always
knows *why* a field is the colour it is.
"""
from schemas.report import CanonicalCheck, CheckStatusColor, ReportField


def test_a_field_not_selected_at_intake_is_grey_with_no_citation_required():
    field = ReportField(
        check=CanonicalCheck.MCA,
        applicable=False,
        selected=False,
        color=CheckStatusColor.GREY,
        reason="Not selected by analyst at intake",
    )

    assert field.color == CheckStatusColor.GREY
    assert field.citation_url is None


def test_a_clean_resolved_field_is_green_and_carries_its_source_citation():
    field = ReportField(
        check=CanonicalCheck.SANCTIONS_PEP,
        applicable=True,
        selected=True,
        color=CheckStatusColor.GREEN,
        reason="No sanctions/PEP match found",
        source_name="OpenSanctions",
        citation_url="https://www.opensanctions.org/search/?q=Suresh+Enterprises",
    )

    assert field.color == CheckStatusColor.GREEN
    assert field.source_name == "OpenSanctions"
    assert field.citation_url is not None
