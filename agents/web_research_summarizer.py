"""
Two helpers backing the per-check web-research flow:
- preview_hits_batch: one short summary per search hit so the analyst can
  skim 10 results quickly before picking which to deep-dive on.
- summarize_selected_hits: the final draft after they've picked, before
  they lock it as a manual finding.

Nothing here produces an EvidenceRecord directly — the analyst reviews
and edits the summary before locking it via /manual-findings.
"""
import json

from tools.groq_client import call_groq

_SYSTEM = (
    "You are drafting a short due-diligence summary for a human analyst to "
    "review. The analyst has selected the sources themselves — do NOT add "
    "sources you weren't given. Do NOT invent facts. Write 2-3 short sentences, "
    "plain prose, no bullets, no markdown. If the sources don't actually answer "
    "the question, say so plainly instead of guessing."
)

_PREVIEW_SYSTEM = (
    "You are summarising individual search results so an analyst can skim "
    "many at once and pick which to deep-dive on. For each result given, "
    "write ONE 2-3 line summary of what that page likely says about the "
    "vendor and the specific check. Do not invent facts beyond what the "
    "snippet shows. If the snippet is thin or off-topic, say so briefly. "
    "Return a JSON array of objects: [{\"url\": \"...\", \"preview\": \"...\"}]. "
    "Nothing else. No markdown, no prose outside the JSON."
)


def preview_hits_batch(
    vendor_name: str,
    check_label: str,
    hits: list[dict],
    groq_api_keys: list[str],
) -> dict[str, str]:
    """
    Takes up to ~10 raw Tavily hits and returns {url: preview_summary} so
    the UI can show a tight AI-written 2-3 line preview per hit instead of
    the raw Tavily snippet. One Groq call, batched, for cost.
    """
    if not hits:
        return {}

    hit_block = "\n\n".join(
        f"[{i + 1}] url: {h.get('url', '')}\n"
        f"title: {h.get('title', '')}\n"
        f"snippet: {h.get('snippet', '')}"
        for i, h in enumerate(hits)
    )
    user_prompt = (
        f"Vendor: {vendor_name}\n"
        f"Check: {check_label}\n\n"
        f"Search results:\n{hit_block}\n\n"
        f"For each result, write a 2-3 line preview describing what the "
        f"page likely says about this vendor's {check_label} posture. "
        f"Return JSON only."
    )

    try:
        raw = call_groq(
            messages=[
                {"role": "system", "content": _PREVIEW_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            api_keys=groq_api_keys,
            max_tokens=3000,
        ).strip()
    except Exception as exc:
        print(f"[preview_hits_batch] Groq call failed: {exc}")
        return {}

    # gpt-oss models can emit visible chain-of-thought before the JSON —
    # pull out the first balanced [...] block instead of trying to parse
    # the whole string.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        print(f"[preview_hits_batch] No JSON array found in response: {raw[:200]!r}")
        return {}

    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        print(f"[preview_hits_batch] JSON parse failed ({exc}): {raw[start:end+1][:200]!r}")
        return {}
    return {
        item["url"]: item["preview"]
        for item in parsed
        if isinstance(item, dict) and "url" in item and "preview" in item
    }


def summarize_selected_hits(
    vendor_name: str,
    check_label: str,
    selected_hits: list[dict],
    groq_api_keys: list[str],
) -> str:
    """
    selected_hits = [{"title": ..., "url": ..., "snippet": ...}, ...]
    Returns the model's draft summary string (editable by the analyst before locking).
    """
    if not selected_hits:
        return ""

    hit_block = "\n\n".join(
        f"[{i + 1}] {h.get('title', '')}\n{h.get('url', '')}\n{h.get('snippet', '')}"
        for i, h in enumerate(selected_hits)
    )

    user_prompt = (
        f"Vendor: {vendor_name}\n"
        f"Check: {check_label}\n\n"
        f"Analyst-selected sources:\n{hit_block}\n\n"
        f"Draft a 2-3 sentence summary of what these sources collectively say "
        f"about this vendor's {check_label} posture. If they don't say anything "
        f"relevant, say that."
    )

    try:
        return call_groq(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            api_keys=groq_api_keys,
            max_tokens=400,
        ).strip()
    except Exception as exc:
        return f"[Summary generation failed: {exc}. Please write the summary manually.]"
