from agents.manual_findings import SOURCE_NAME as MANUAL_FINDING_SOURCE_NAME
from schemas.evidence import EvidenceRecord, FindingTag
from schemas.report import CanonicalCheck, CheckStatusColor, Report, ReportField
from schemas.vendor import EntityType

# Two records can share the same FindingCategory (Tavily's adverse-media hit
# and Indian Kanoon's case search are both tagged LITIGATION) but belong to
# different canonical checks — so this maps by source, the field that's
# actually unique per tool, not by category.
SOURCE_NAME_TO_CHECK = {
    "PAN format check": CanonicalCheck.PAN_VERIFICATION,
    "eKYC Now (PAN)": CanonicalCheck.PAN_VERIFICATION,
    "OpenSanctions": CanonicalCheck.SANCTIONS_PEP,
    "Tavily web search": CanonicalCheck.ADVERSE_MEDIA,
    "Indian Kanoon": CanonicalCheck.ECOURTS,
    "MCA (data.gov.in)": CanonicalCheck.MCA,
    "eKYC Now (MCA/CIN)": CanonicalCheck.MCA,
    "eKYC Now (GST)": CanonicalCheck.GST,
    "eKYC Now (Udyam)": CanonicalCheck.MSME_UDYAM,
    "IBBI CIRP dataset": CanonicalCheck.NCLT,
    "OpenSanctions (NSE debarred)": CanonicalCheck.NSE,
    "Analyst UBO trace": CanonicalCheck.UBO_TRACE,
}

# Reserved for source_reference-based routing when more than one finding
# shares a source_name. Currently empty — the UBO tile is routed by
# source_name="Analyst UBO trace" instead.
SOURCE_REFERENCE_TO_CHECK: dict = {}


def _check_for_record(record: EvidenceRecord):
    if record.source_reference in SOURCE_REFERENCE_TO_CHECK:
        return SOURCE_REFERENCE_TO_CHECK[record.source_reference]
    if record.source_name == MANUAL_FINDING_SOURCE_NAME:
        return CanonicalCheck(record.source_reference)
    return SOURCE_NAME_TO_CHECK.get(record.source_name)


_GREEN_TAGS = {FindingTag.RESOLVED_CLEAN, FindingTag.CONFIRMED_BY_ABSENCE}
_AMBER_TAGS = {FindingTag.UNRESOLVED, FindingTag.VENDOR_DECLARED}


def _color_for_tag(tag: FindingTag) -> CheckStatusColor:
    if tag in _GREEN_TAGS:
        return CheckStatusColor.GREEN
    if tag == FindingTag.RESOLVED_RED_FLAG:
        return CheckStatusColor.RED
    return CheckStatusColor.AMBER

ALWAYS_ON_CHECKS = ["global_compliance", "litigation", "india_regulatory"]

REGISTERED_ENTITY_TYPES = {
    EntityType.LLP,
    EntityType.OPC,
    EntityType.PRIVATE_LIMITED,
    EntityType.PUBLIC_LIMITED,
}

COMPANIES_ACT_ENTITY_TYPES = {
    EntityType.OPC,
    EntityType.PRIVATE_LIMITED,
    EntityType.PUBLIC_LIMITED,
}

NCLT_ELIGIBLE_ENTITY_TYPES = COMPANIES_ACT_ENTITY_TYPES | {EntityType.LLP}


def plan_checks(entity_type: EntityType) -> list[str]:
    """
    Decides which checks apply to a vendor based on entity type.

    Sole proprietorships, partnerships, and HUFs have no MCA filing to
    look up, so that check is skipped rather than run and always come
    back empty.
    """
    checks = list(ALWAYS_ON_CHECKS)
    if entity_type in REGISTERED_ENTITY_TYPES:
        checks.append("mca_sebi_nse_bse")
    return checks


def _applicability(entity_type: EntityType, has_physical_premises: bool) -> dict:
    """check -> (applicable, reason)"""
    is_foreign = entity_type == EntityType.FOREIGN_ENTITY
    is_registered = entity_type in REGISTERED_ENTITY_TYPES
    is_public = entity_type == EntityType.PUBLIC_LIMITED
    is_companies_act = entity_type in COMPANIES_ACT_ENTITY_TYPES
    is_nclt_eligible = entity_type in NCLT_ELIGIBLE_ENTITY_TYPES
    is_huf = entity_type == EntityType.HUF
    entity_label = entity_type.value.replace("_", " ").title()

    # Every India-specific registry/scheme check (PAN, GST, MCA, SEBI/NSE/BSE,
    # NCLT, EPFO/ESIC, SFIO, CIBIL, Udyam) is structurally not applicable to
    # an entity incorporated outside India — there's no Indian filing to look
    # up, same reasoning as "sole proprietorship has no MCA filing".
    foreign_reason = f"{entity_label} is incorporated outside India — not applicable"

    mca_reason = (
        "Registered with MCA under the Companies Act / LLP Act"
        if is_registered
        else f"{entity_label} has no MCA filing — not applicable"
    )
    exchange_reason = (
        "Publicly listed companies are checked against exchange filings"
        if is_public
        else "Only public limited companies can be listed on an exchange"
    )
    gst_mca_filing_reason = (
        "Derived from GST + MCA filing history"
        if is_registered
        else "Derived from GST filing history (no MCA filing for this entity type)"
    )

    return {
        # Entity resolution
        CanonicalCheck.PAN_VERIFICATION: (
            not is_foreign,
            foreign_reason if is_foreign else "PAN format/identity check applies to every Indian entity type",
        ),
        # Global compliance
        CanonicalCheck.SANCTIONS_PEP: (
            True,
            "Sanctions/PEP screening applies to every entity type",
        ),
        CanonicalCheck.ADVERSE_MEDIA: (
            True,
            "Adverse media search applies to every entity type",
        ),
        # India regulatory
        CanonicalCheck.GST: (
            not is_foreign,
            foreign_reason if is_foreign else "GST registration applies to every Indian entity type",
        ),
        CanonicalCheck.MCA: (is_registered and not is_foreign, foreign_reason if is_foreign else mca_reason),
        CanonicalCheck.SEBI: (is_public and not is_foreign, foreign_reason if is_foreign else exchange_reason),
        CanonicalCheck.NCLT: (
            is_nclt_eligible and not is_foreign,
            foreign_reason
            if is_foreign
            else (
                "Corporate insolvency (IBC) applies to registered companies and LLPs"
                if is_nclt_eligible
                else f"{entity_label} cannot be taken to NCLT — not applicable"
            ),
        ),
        CanonicalCheck.EPFO: (
            not is_foreign,
            foreign_reason if is_foreign else "EPF registration applies to every Indian entity type",
        ),
        CanonicalCheck.ESIC: (
            not is_foreign,
            foreign_reason if is_foreign else "ESI registration applies to every Indian entity type",
        ),
        CanonicalCheck.SFIO: (
            is_companies_act and not is_foreign,
            foreign_reason
            if is_foreign
            else (
                "SFIO investigates fraud under the Companies Act"
                if is_companies_act
                else f"{entity_label} is not a Companies Act entity — not applicable"
            ),
        ),
        CanonicalCheck.RBI_CIBIL: (
            not is_foreign,
            foreign_reason if is_foreign else "Credit history check applies to every Indian entity type",
        ),
        CanonicalCheck.NSE: (is_public and not is_foreign, foreign_reason if is_foreign else exchange_reason),
        CanonicalCheck.BSE: (is_public and not is_foreign, foreign_reason if is_foreign else exchange_reason),
        CanonicalCheck.MSME_UDYAM: (
            not is_foreign,
            foreign_reason if is_foreign else "MSME/Udyam registration applies to every Indian entity type",
        ),
        CanonicalCheck.FACTORY_TRADE_LICENCE: (
            has_physical_premises,
            "Required for vendors with physical premises"
            if has_physical_premises
            else "No physical premises declared — not applicable",
        ),
        # Litigation
        CanonicalCheck.ECOURTS: (True, "Any entity type can be a named party in a case"),
        # Ownership
        CanonicalCheck.UBO_TRACE: (
            not is_huf,
            "Traces beneficial ownership above the SBO threshold"
            if not is_huf
            else "HUF members are the owners by definition — no UBO trace needed",
        ),
        # Reasoning-only — derived from checks already run above
        CanonicalCheck.FILING_DISCIPLINE: (
            not is_foreign,
            foreign_reason if is_foreign else gst_mca_filing_reason,
        ),
        CanonicalCheck.OPERATING_TENURE: (
            not is_foreign,
            foreign_reason if is_foreign else "Derived from MCA/GST registration date",
        ),
        CanonicalCheck.TURNOVER_BAND: (
            not is_foreign,
            foreign_reason if is_foreign else "Derived from MSME/Udyam enterprise category",
        ),
        CanonicalCheck.LICENCE_DOCUMENT_GAPS: (
            True,
            "Derived from factory/trade licence status + intake-form uploads",
        ),
    }


def route_checks(entity_type: EntityType, has_physical_premises: bool) -> list[ReportField]:
    """
    At intake, before any check runs, decide which of the 12 canonical
    checks (plus global compliance) apply to this vendor's entity type and
    say why. Every field starts unrun: selected=True, color=GREY. The
    analyst can flip `selected` off before the pipeline starts.
    """
    applicability = _applicability(entity_type, has_physical_premises)
    return [
        ReportField(
            check=check,
            applicable=applicable,
            selected=True,
            color=CheckStatusColor.GREY,
            reason=reason,
        )
        for check, (applicable, reason) in applicability.items()
    ]


def apply_overrides(
    fields: list[ReportField], deselected_checks: list[CanonicalCheck]
) -> list[ReportField]:
    """
    Analyst-driven step between route_checks and running the pipeline:
    turns off any checks the analyst chose to skip. Deselecting a check
    that was never applicable is a no-op — it's already off.
    """
    deselected = set(deselected_checks)
    return [
        field.model_copy(update={"selected": False}) if field.check in deselected else field
        for field in fields
    ]


def build_report(
    vendor_id: str,
    routed_fields: list[ReportField],
    records: list[EvidenceRecord],
    score: float,
    recommendation: str,
    score_reasons: list[str] | None = None,
) -> Report:
    """
    Combines the intake routing decisions with whatever evidence records
    the pipeline actually produced into the final per-check report.

    A field stays grey if it was never selected, was never applicable, or
    is selected+applicable but no matching record came back yet (category
    not wired to a canonical check, or the agent hasn't run). Otherwise its
    colour and citation come straight from the matching record.
    """
    records_by_check = {}
    for record in records:
        check = _check_for_record(record)
        if check is not None:
            records_by_check[check] = record

    result_fields = []
    for field in routed_fields:
        if not field.selected or not field.applicable:
            result_fields.append(field.model_copy(update={"color": CheckStatusColor.GREY}))
            continue

        record = records_by_check.get(field.check)
        if record is None:
            result_fields.append(
                field.model_copy(
                    update={
                        "color": CheckStatusColor.GREY,
                        "reason": "Selected and applicable, but not yet run",
                    }
                )
            )
            continue

        result_fields.append(
            field.model_copy(
                update={
                    "color": _color_for_tag(record.tag),
                    "reason": record.summary,
                    "source_name": record.source_name,
                    "citation_url": record.citation_url,
                    "supporting_citations": record.supporting_citations,
                }
            )
        )

    return Report(
        vendor_id=vendor_id,
        fields=result_fields,
        score=score,
        recommendation=recommendation,
        score_reasons=score_reasons or [],
    )
