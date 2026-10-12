import json
import urllib.parse
import urllib.request

INDIAN_KANOON_URL = "https://api.indiankanoon.org/search/"


def _search(query: str, api_key: str) -> dict:
    data = f"formInput={urllib.parse.quote(query)}".encode("utf-8")
    req = urllib.request.Request(INDIAN_KANOON_URL, data=data, method="POST")
    req.add_header("Authorization", f"Token {api_key}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Mozilla/5.0 poc-due-diligence/1.0")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Topic queries we run per vendor name. NI Act 138 catches cheque-bounce;
# the others catch SFIO / IBC / NCLT and criminal-complaint chatter the
# earlier single-topic query missed entirely for distressed vendors.
_QUERY_TOPICS = [
    "cheque bounce NI Act 138",
    "fraud",
    "money laundering",
    "insolvency NCLT IBC",
]


def ecourts_case_search(name: str, api_key: str) -> list[dict]:
    """
    Runs each topic query against Indian Kanoon and returns the docs whose
    title actually names the vendor, deduped by tid. The raw queries also
    return generic same-topic noise (other parties' cases), so the title
    filter is what turns that into vendor-specific hits for the litigation
    agent to classify.
    """
    seen_tids: set = set()
    matched: list[dict] = []
    for topic in _QUERY_TOPICS:
        response = _search(f"{name} {topic}", api_key)
        for doc in response.get("docs", []):
            tid = doc.get("tid")
            if tid in seen_tids:
                continue
            if name.lower() not in doc.get("title", "").lower():
                continue
            seen_tids.add(tid)
            matched.append(doc)
    return matched
