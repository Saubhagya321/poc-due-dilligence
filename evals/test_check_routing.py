"""
Seam under test: orchestrator.route_checks(vendor) — at intake, before any
API call runs, decide which of the 12 canonical checks apply to this
vendor's entity type, and say why. This is what the analyst sees on the
intake screen so they know up front which checks will run and which are
being skipped as not applicable.

Rules taken from the spec's entity-type routing table:
- MCA/CIN: only registered entities (LLP, OPC, private ltd, public ltd) —
  sole prop, partnership, HUF have no MCA filing to look up.
- SEBI/NSE/BSE: only public limited companies can be listed; every other
  entity type (including private limited, which could pursue an IPO but
  hasn't) is marked not applicable at this stage.
- GST, EPFO, ESIC, RBI/CIBIL, MSME/Udyam: every entity type can register
  for these, so they're applicable regardless of entity type.
- Factory/trade licence: only applicable when the vendor declared physical
  premises.
- eCourts/litigation search: every entity type can be a named party in a
  case, so always applicable.
- NCLT (corporate insolvency) and SFIO (Companies Act fraud investigation):
  only apply to registered companies (OPC, private ltd, public ltd); LLPs
  can be wound up too but aren't investigated by SFIO, so NCLT includes LLP
  and SFIO does not.
- Global compliance (sanctions/PEP + adverse media): always applicable,
  every entity type, no registry needed.

Every returned field starts out `selected=True` and `color=GREY` — nothing
has run yet at intake. The analyst can flip `selected` off before the
pipeline starts; that override, and turning a run result into a colour,
are separate seams (not this one).
"""
from schemas.report import CanonicalCheck, CheckStatusColor
from schemas.vendor import EntityType
from orchestrator.orchestrator import route_checks


def _reason_for(fields, check):
    return next(f for f in fields if f.check == check)


def test_sole_proprietorship_has_no_mca_or_sebi_but_has_gst_and_global_compliance():
    fields = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)

    mca = _reason_for(fields, CanonicalCheck.MCA)
    sebi = _reason_for(fields, CanonicalCheck.SEBI)
    gst = _reason_for(fields, CanonicalCheck.GST)
    sanctions_pep = _reason_for(fields, CanonicalCheck.SANCTIONS_PEP)
    adverse_media = _reason_for(fields, CanonicalCheck.ADVERSE_MEDIA)

    assert mca.applicable is False
    assert "no MCA filing" in mca.reason or "not applicable" in mca.reason.lower()
    assert sebi.applicable is False
    assert gst.applicable is True
    assert sanctions_pep.applicable is True
    assert adverse_media.applicable is True

    for field in fields:
        assert field.selected is True
        assert field.color == CheckStatusColor.GREY


def test_public_limited_company_is_applicable_for_mca_sebi_nclt_and_sfio():
    fields = route_checks(entity_type=EntityType.PUBLIC_LIMITED, has_physical_premises=False)

    assert _reason_for(fields, CanonicalCheck.MCA).applicable is True
    assert _reason_for(fields, CanonicalCheck.SEBI).applicable is True
    assert _reason_for(fields, CanonicalCheck.NCLT).applicable is True
    assert _reason_for(fields, CanonicalCheck.SFIO).applicable is True


def test_llp_is_applicable_for_nclt_but_not_sfio():
    fields = route_checks(entity_type=EntityType.LLP, has_physical_premises=False)

    assert _reason_for(fields, CanonicalCheck.NCLT).applicable is True
    assert _reason_for(fields, CanonicalCheck.SFIO).applicable is False


def test_factory_trade_licence_only_applicable_when_vendor_declared_physical_premises():
    with_premises = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=True)
    without_premises = route_checks(entity_type=EntityType.SOLE_PROPRIETORSHIP, has_physical_premises=False)

    assert _reason_for(with_premises, CanonicalCheck.FACTORY_TRADE_LICENCE).applicable is True
    assert _reason_for(without_premises, CanonicalCheck.FACTORY_TRADE_LICENCE).applicable is False
