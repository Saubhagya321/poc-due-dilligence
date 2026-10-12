"""
Takes extracted document markdown + the check context + vendor name,
asks Groq whether the doc supports / contradicts / is irrelevant to the
check, and returns a draft (tag, summary) for the analyst to review.

Intentionally returns a draft — nothing is auto-locked as an
EvidenceRecord. The analyst edits and confirms via /manual-findings,
same guardrail bar as any other manual finding.

The system prompt is CHECK-SPECIFIC: a GST cert, a CIBIL report and a
factory licence need totally different "what's clean / amber / red"
criteria. See agents/document_check_prompts.py for the per-check prompts.
"""
import json

from agents.document_check_prompts import CHECK_PROMPTS, COMMON_CONTRACT
from schemas.report import CanonicalCheck
from tools.groq_client import call_groq


_FALLBACK_SYSTEM = (
    "You are helping a due-diligence analyst classify an uploaded supporting "
    "document. Decide the tag ('resolved-clean' / 'resolved-red-flag' / "
    "'unresolved') and a 2-3 sentence summary quoting specific values from "
    "the document.\n"
    f"{COMMON_CONTRACT}"
)


def classify_document(
    vendor_name: str,
    check: CanonicalCheck,
    check_label: str,
    extracted_markdown: str,
    groq_api_keys: list[str],
    max_chars: int = 12000,
) -> dict:
    """
    Returns {"tag": str, "summary": str}. On any failure returns an
    unresolved placeholder so the UI never crashes on a bad doc.
    """
    truncated = extracted_markdown[:max_chars]
    if len(extracted_markdown) > max_chars:
        truncated += f"\n\n[... document truncated at {max_chars} chars for the model ...]"

    user_prompt = (
        f"Vendor: {vendor_name}\n"
        f"Check being verified: {check_label}\n\n"
        f"Extracted document text:\n---\n{truncated}\n---\n\n"
        f"Classify this document per the instructions. Return JSON only."
    )

    system_prompt = CHECK_PROMPTS.get(check, _FALLBACK_SYSTEM)
    try:
        raw = call_groq(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            api_keys=groq_api_keys,
            max_tokens=600,
        ).strip()
    except Exception as exc:
        return {
            "tag": "unresolved",
            "summary": f"Model classification failed: {exc}. Please review the document manually.",
        }

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # gpt-oss may emit chain-of-thought before the JSON object — grab the
    # first balanced {...} block instead of parsing the whole string.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {
            "tag": "unresolved",
            "summary": f"Model returned no JSON object. Raw: {raw[:200]}",
        }
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {
            "tag": "unresolved",
            "summary": f"Model returned invalid JSON. Raw: {raw[start:end+1][:200]}",
        }
    tag = parsed.get("tag", "unresolved")
    summary = parsed.get("summary", "No summary returned.")
    if tag not in {"resolved-clean", "resolved-red-flag", "unresolved"}:
        tag = "unresolved"
    return {"tag": tag, "summary": summary}
