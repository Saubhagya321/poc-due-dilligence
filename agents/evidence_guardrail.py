from schemas.evidence import EvidenceRecord, FindingTag


def review_evidence_citations(
    records: list[EvidenceRecord],
) -> tuple[list[EvidenceRecord], list[EvidenceRecord]]:
    """
    Splits findings into (accepted, rejected) before they reach the report.

    Only a red flag makes an accusation someone would need to verify, so
    only red flags are held to the "must have a clickable citation" bar.
    """
    accepted: list[EvidenceRecord] = []
    rejected: list[EvidenceRecord] = []

    for record in records:
        if record.tag == FindingTag.RESOLVED_RED_FLAG and not record.citation_url:
            rejected.append(record)
        else:
            accepted.append(record)

    return accepted, rejected
