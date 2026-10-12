import json
import urllib.error
import urllib.request
from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)

OPENSANCTIONS_URL = "https://api.opensanctions.org/match/default"

# Stopwords stripped when building the anchor-token filter for OpenSanctions
# matches. OpenSanctions' matcher is fuzzy — a query for "Q3 InfoTech Pvt. Ltd."
# can return "Ecospace Infotech", "KPT Infotech", "Goglet Infotech" at tied
# top scores, all three on the NSE debarred list, all three completely
# unrelated to Q3. Without this filter we'd flag amber on 3 wrong entities
# instead of saying "no match."
_NAME_STOPWORDS = {
    "the", "and", "of", "for", "co", "company", "corp", "corporation",
    "limited", "ltd", "private", "pvt", "llp", "inc", "incorporated",
    "international", "india", "indian", "group", "holdings",
}


def _anchor_tokens(name: str) -> list[str]:
    lowered = name.lower().replace("&", " ").replace(",", " ").replace(".", " ")
    tokens = [t for t in lowered.split() if t and t not in _NAME_STOPWORDS]
    return tokens[:2]


def _hit_matches_vendor(hit: dict, anchors: list[str]) -> bool:
    """
    A tied-top-score hit is only kept if the vendor's distinctive tokens
    actually appear in the match caption. "Q3 InfoTech" with anchors
    ['q3', 'infotech'] rejects "Ecospace Infotech" (missing 'q3') but
    accepts "Q3 Infotech Pvt Ltd" cleanly.
    """
    if not anchors:
        return True
    haystack = (hit.get("caption", "") + " " + " ".join(hit.get("properties", {}).get("name", []))).lower()
    return all(a in haystack for a in anchors)


def _search(name: str, api_key: str, schema: str = "Person") -> dict:
    payload = {"queries": {"q1": {"schema": schema, "properties": {"name": [name]}}}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OPENSANCTIONS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"ApiKey {api_key}")
    req.add_header("User-Agent", "Mozilla/5.0 poc-due-diligence/1.0")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return body["responses"]["q1"]


def _red_flag_record(vendor_id: str, match: dict) -> EvidenceRecord:
    topics = match["properties"].get("topics", [])
    datasets = match.get("datasets", [])
    source_urls = match["properties"].get("sourceUrl", [])

    return EvidenceRecord(
        vendor_id=vendor_id,
        category=FindingCategory.GLOBAL_COMPLIANCE,
        source_name="OpenSanctions",
        source_reference=match["id"],
        summary=(
            f"Matched '{match['caption']}' (topics: {', '.join(topics) or 'none'}) "
            f"in datasets: {', '.join(datasets) or 'none'}."
        ),
        tag=FindingTag.RESOLVED_RED_FLAG,
        confidence_tier=ConfidenceTier.TIER_2,
        as_of_date=date.today(),
        check_status=CheckStatus.SUCCESS,
        # Some OpenSanctions datasets (e.g. NSE debarred) don't expose a
        # sourceUrl — fall back to the entity page so the citation guardrail
        # (which drops red flags without a URL) doesn't swallow a real match.
        citation_url=source_urls[0] if source_urls else f"https://www.opensanctions.org/entities/{match['id']}/",
    )


def sanctions_pep_screen(vendor_id: str, name: str, pan: str | None, api_key: str) -> EvidenceRecord:
    """
    Screens a name against OpenSanctions and classifies the result.

    A tied top score across different entity IDs (e.g. common Indian names
    like "Suresh Kumar" matching several unrelated real people/entities at
    the same score) can't be auto-resolved by name alone. If the vendor's
    own PAN matches one tied candidate's taxNumber, that confirms identity
    and resolves the tie. Otherwise it's flagged as ambiguous so a human
    confirms it, per the spec's rule that low-confidence or tied matches
    route to a person, not a retry.
    """
    try:
        response = _search(name, api_key)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        # A 429 or network error must not take the whole screening down —
        # record a technical failure so the UI shows "sanctions check
        # temporarily unavailable" instead of a 500.
        detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else str(exc)
        return EvidenceRecord(
            vendor_id=vendor_id,
            category=FindingCategory.GLOBAL_COMPLIANCE,
            source_name="OpenSanctions",
            source_reference="technical-failure",
            summary=f"OpenSanctions screening for '{name}' failed: {detail}. Retry needed.",
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.TECHNICAL_FAILURE,
        )
    results = response.get("results", [])

    # OpenSanctions' matcher is fuzzy enough that it can tie 3 unrelated
    # entities at a mid score (e.g. 0.75) just because they share a common
    # suffix like "Infotech Pvt. Ltd." Drop any result where the vendor's
    # distinctive first-token(s) don't actually appear in the candidate's
    # caption/name. If this empties the result set, treat as a clean no-match
    # instead of pretending there was ambiguity.
    anchors = _anchor_tokens(name)
    filtered_results = [r for r in results if _hit_matches_vendor(r, anchors)]

    if not filtered_results:
        return EvidenceRecord(
            vendor_id=vendor_id,
            category=FindingCategory.GLOBAL_COMPLIANCE,
            source_name="OpenSanctions",
            source_reference="no-match",
            summary=f"No sanctions or PEP matches found for '{name}'.",
            tag=FindingTag.RESOLVED_CLEAN,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.SUCCESS,
        )

    results = filtered_results
    top_score = results[0]["score"]
    tied = [r for r in results if r["score"] == top_score]
    tied_ids = {r["id"] for r in tied}

    if len(tied_ids) > 1:
        pan_matches = [r for r in tied if pan in r["properties"].get("taxNumber", [])]
        if len(pan_matches) == 1:
            return _red_flag_record(vendor_id, pan_matches[0])

        return EvidenceRecord(
            vendor_id=vendor_id,
            category=FindingCategory.GLOBAL_COMPLIANCE,
            source_name="OpenSanctions",
            source_reference=", ".join(sorted(tied_ids)),
            summary=(
                f"{len(tied_ids)} different entities tied at the top match "
                f"score ({top_score}) for '{name}' — identity needs human "
                "confirmation before this can be marked clean or a red flag."
            ),
            tag=FindingTag.UNRESOLVED,
            confidence_tier=ConfidenceTier.TIER_2,
            as_of_date=date.today(),
            check_status=CheckStatus.AMBIGUOUS_MATCH,
        )

    return _red_flag_record(vendor_id, results[0])
