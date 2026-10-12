from schemas.evidence import EvidenceRecord, FindingCategory, FindingTag, SupportingCitation
from schemas.vendor import VendorIntake
from tools.opensanctions import sanctions_pep_screen
from tools.tavily_search import adverse_media_search

# Worst-tag-wins order when collapsing entity + key-person sanctions results
# into a single sanctions_pep record. A key-person red flag has to beat an
# entity-clean result so a Gitanjali/Choksi style promoter risk isn't masked.
_TAG_SEVERITY = {
    FindingTag.RESOLVED_RED_FLAG: 4,
    FindingTag.UNRESOLVED: 3,
    FindingTag.VENDOR_DECLARED: 2,
    FindingTag.CONFIRMED_BY_ABSENCE: 1,
    FindingTag.RESOLVED_CLEAN: 0,
}


def _combine_sanctions_results(
    entity_name: str,
    entity_record: EvidenceRecord,
    person_records: list[tuple[str, EvidenceRecord]],
) -> EvidenceRecord:
    """
    Collapses the entity sanctions result + one result per key-person into a
    single sanctions_pep record. Worst tag wins; each name screened is listed
    as a supporting citation so the analyst can see what matched where.
    """
    worst_tag = entity_record.tag
    worst_record = entity_record
    for _, rec in person_records:
        if _TAG_SEVERITY[rec.tag] > _TAG_SEVERITY[worst_tag]:
            worst_tag = rec.tag
            worst_record = rec

    all_screened = [(entity_name, entity_record)] + person_records
    citations = [
        SupportingCitation(
            title=name,
            url=rec.citation_url or "https://www.opensanctions.org/search/",
            source=f"OpenSanctions — {rec.tag.value}",
        )
        for name, rec in all_screened
    ]

    return entity_record.model_copy(update={
        "tag": worst_tag,
        "summary": worst_record.summary,
        "citation_url": worst_record.citation_url or entity_record.citation_url,
        "source_reference": worst_record.source_reference,
        "supporting_citations": citations,
    })


def screen_global_compliance(
    vendor: VendorIntake,
    opensanctions_api_key: str,
    tavily_api_key: str,
) -> list[EvidenceRecord]:
    """Runs every global-compliance check for a vendor and returns each finding."""
    entity_sanctions = sanctions_pep_screen(
        vendor_id=vendor.vendor_id,
        name=vendor.name,
        pan=vendor.pan,
        api_key=opensanctions_api_key,
    )
    person_results: list[tuple[str, EvidenceRecord]] = []
    for person in vendor.key_persons:
        rec = sanctions_pep_screen(
            vendor_id=vendor.vendor_id,
            name=person,
            pan=None,  # a director's personal PAN isn't a vendor-level field
            api_key=opensanctions_api_key,
        )
        person_results.append((person, rec))

    sanctions_record = (
        _combine_sanctions_results(vendor.name, entity_sanctions, person_results)
        if person_results
        else entity_sanctions
    )

    media_record = adverse_media_search(
        vendor_id=vendor.vendor_id, name=vendor.name, api_key=tavily_api_key
    )

    findings = [sanctions_record, media_record]

    # OpenSanctions already pulls the NSE debarred list via in_nse_debarred.
    # When a vendor hits that specific dataset, duplicate the finding into an
    # NSE-tile record too — this auto-populates the NSE tile from data we're
    # already paying nothing for, instead of scraping nseindia.com (Akamai
    # anti-bot). Only applicable entity types will actually have the tile
    # rendered; others drop it silently.
    if (
        sanctions_record.tag == FindingTag.RESOLVED_RED_FLAG
        and "in_nse_debarred" in sanctions_record.summary
    ):
        findings.append(
            sanctions_record.model_copy(update={
                "source_name": "OpenSanctions (NSE debarred)",
                "category": FindingCategory.INDIA_REGULATORY,
            })
        )

    return findings
