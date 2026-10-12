import json
import urllib.request
from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
)

TAVILY_URL = "https://api.tavily.com/search"

# Tavily returns results for almost any query, even when nothing relevant
# exists — a generic company name pulls in unrelated news noise scored well
# below this line (observed: 0.05-0.33), while a real fraud case scores well
# above it (observed: 0.68-0.89). Without this filter, "got results back"
# would false-flag any vendor with a common name.
RELEVANCE_THRESHOLD = 0.5


def _search(
    query: str,
    api_key: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
) -> dict:
    payload: dict = {"api_key": api_key, "query": query, "max_results": max_results}
    if include_domains:
        payload["include_domains"] = include_domains
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(TAVILY_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 poc-due-diligence/1.0")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Filler words to strip when building the vendor-name anchor for filtering.
# Keeps the distinctive tokens that actually identify the entity.
_NAME_STOPWORDS = {
    "the", "and", "of", "for", "co", "company", "corp", "corporation",
    "limited", "ltd", "private", "pvt", "llp", "inc", "incorporated",
    "international", "india", "indian", "group", "holdings",
}


def _name_anchor_tokens(name: str) -> list[str]:
    """
    First two distinctive (non-filler) tokens of the vendor name. Used to
    reject site-restricted hits that happen to come from the right domain
    but are about a different entity — SEBI's archive scoring hits 0.99 for
    unrelated filings; this filter forces at least two name tokens to
    appear in the title or snippet before we return the hit.
    """
    lowered = name.lower().replace("&", " ").replace(",", " ").replace(".", " ")
    tokens = [t for t in lowered.split() if t and t not in _NAME_STOPWORDS]
    return tokens[:2]


def site_restricted_search(
    query: str,
    api_key: str,
    include_domains: list[str],
    max_results: int = 10,
    require_name_in_hit: str | None = None,
) -> list[dict]:
    """
    Returns up to `max_results` {title, url, snippet, score} dicts restricted
    to the given domains. When `require_name_in_hit` is set, drop hits that
    don't carry the vendor's distinctive tokens in the title or snippet —
    Tavily's own relevance score reflects site+query token match, not
    whether the page is about THIS vendor, so unfiltered results on big
    archives like SEBI/NSE/BSE are mostly noise about other entities.
    """
    response = _search(
        query=query, api_key=api_key, max_results=max_results, include_domains=include_domains
    )
    raw = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:400],
            "score": r.get("score", 0.0),
        }
        for r in response.get("results", [])
    ]
    if not require_name_in_hit:
        return raw

    anchors = _name_anchor_tokens(require_name_in_hit)
    if not anchors:
        return raw

    filtered = []
    for hit in raw:
        haystack = f"{hit['title']} {hit['snippet']}".lower()
        if all(anchor in haystack for anchor in anchors):
            filtered.append(hit)
    return filtered


def adverse_media_search(vendor_id: str, name: str, api_key: str) -> EvidenceRecord:
    """
    Searches the open web for fraud/bribery/cheating mentions of a name.

    Tavily is a general web scraper with no official provenance and no way
    to confirm an article is actually about this vendor rather than a
    same-named one (proved live: "Suresh Enterprises" pulled back an
    unrelated Facebook complaint at score 0.572). So a relevant hit is never
    auto-flagged red — it's unresolved until a human checks the article
    against the vendor's PAN. Finding nothing relevant is confirmed-by-absence,
    not resolved-clean — we looked and found no adverse media, which is
    weaker than an official registry saying "no record".
    """
    query = f"{name} fraud bribery cheating case scam"
    response = _search(query, api_key)
    results = response.get("results", [])

    relevant = [r for r in results if r.get("score", 0) >= RELEVANCE_THRESHOLD]

    if not relevant:
        return EvidenceRecord(
            vendor_id=vendor_id,
            category=FindingCategory.LITIGATION,
            source_name="Tavily web search",
            source_reference="no-relevant-hits",
            summary=f"No credible adverse media found for '{name}'.",
            tag=FindingTag.CONFIRMED_BY_ABSENCE,
            confidence_tier=ConfidenceTier.TIER_3,
            as_of_date=date.today(),
            check_status=CheckStatus.SUCCESS,
        )

    top = relevant[0]
    return EvidenceRecord(
        vendor_id=vendor_id,
        category=FindingCategory.LITIGATION,
        source_name="Tavily web search",
        source_reference=top["url"],
        summary=(
            f"'{top['title']}' — {top['content'][:200]} "
            "(identity not confirmed — needs human cross-check against vendor PAN)"
        ),
        tag=FindingTag.UNRESOLVED,
        confidence_tier=ConfidenceTier.TIER_3,
        as_of_date=date.today(),
        check_status=CheckStatus.AMBIGUOUS_MATCH,
        citation_url=top["url"],
    )
