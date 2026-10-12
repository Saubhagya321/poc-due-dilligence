from collections import defaultdict

from schemas.evidence import EvidenceRecord, FindingTag
from schemas.report import RecommendedAction, ScoringResult

CATEGORY_WEIGHT = 25.0
PROCEED_THRESHOLD = 75.0
SAFEGUARDS_THRESHOLD = 40.0


def _record_points(record: EvidenceRecord) -> float:
    if record.tag in (FindingTag.RESOLVED_CLEAN, FindingTag.CONFIRMED_BY_ABSENCE):
        return CATEGORY_WEIGHT
    if record.tag == FindingTag.UNRESOLVED:
        return CATEGORY_WEIGHT / 2
    return 0.0  # vendor-declared, resolved-red-flag


def _dedupe_records(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """
    Collapse duplicate records keyed by (source_name, source_reference) +
    summary. The same OpenSanctions hit can get emitted twice when a name
    appears in both the vendor's `key_persons` list and in a locked UBO
    graph (both paths screen it independently). Keeping both inflates the
    "Why this score" trace with repeated identical reasons.
    """
    seen: set[tuple] = set()
    deduped: list[EvidenceRecord] = []
    for r in records:
        key = (r.source_name, r.source_reference, r.tag.value, r.summary)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def score_vendor(vendor_id: str, records: list[EvidenceRecord]) -> ScoringResult:
    """
    A confirmed sanctions/PEP match is a hard override: no combination of
    clean findings elsewhere can outweigh that risk, so it declines
    immediately without going through weighted scoring.

    Otherwise, the score is a percentage of the categories actually
    checked (not a fixed set of 4) — a vendor shouldn't be scored down
    for categories no agent has run yet.
    """
    records = _dedupe_records(records)
    sanctions_hits = [
        r
        for r in records
        if r.tag == FindingTag.RESOLVED_RED_FLAG and r.source_name == "OpenSanctions"
    ]
    if sanctions_hits:
        return ScoringResult(
            vendor_id=vendor_id,
            recommendation=RecommendedAction.DECLINE,
            score=0.0,
            reasons=[f"Sanctions/PEP match: {r.summary}" for r in sanctions_hits],
        )

    reasons: list[str] = []
    points_by_category: dict = defaultdict(list)

    for record in records:
        points_by_category[record.category].append(_record_points(record))
        if record.tag == FindingTag.UNRESOLVED:
            reasons.append(f"Unresolved, needs human review: {record.summary}")
        elif record.tag == FindingTag.VENDOR_DECLARED:
            reasons.append(f"Vendor did not provide: {record.summary}")
        elif record.tag == FindingTag.RESOLVED_RED_FLAG:
            reasons.append(f"Red flag: {record.summary}")

    if not points_by_category:
        score = 0.0
    else:
        category_scores = [sum(pts) / len(pts) for pts in points_by_category.values()]
        score = sum(category_scores) / (len(category_scores) * CATEGORY_WEIGHT) * 100

    if score >= PROCEED_THRESHOLD:
        recommendation = RecommendedAction.PROCEED
    elif score >= SAFEGUARDS_THRESHOLD:
        recommendation = RecommendedAction.PROCEED_WITH_SAFEGUARDS
    else:
        recommendation = RecommendedAction.DECLINE

    has_unresolved = any(r.tag == FindingTag.UNRESOLVED for r in records)
    if has_unresolved and recommendation == RecommendedAction.PROCEED:
        # An unresolved finding means a human hasn't confirmed it yet — a
        # high average score shouldn't be able to silently wave that
        # through as a clean proceed; it stays gated until a human clears it.
        recommendation = RecommendedAction.PROCEED_WITH_SAFEGUARDS

    return ScoringResult(
        vendor_id=vendor_id, recommendation=recommendation, score=score, reasons=reasons
    )
