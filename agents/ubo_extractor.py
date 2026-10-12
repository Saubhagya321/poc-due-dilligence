"""
Takes extracted document text and/or an analyst's typed description and
returns an OwnershipGraph. Deliberately dumb — the analyst reviews and
edits the result in the UI before locking.
"""
import json

from schemas.ubo import OwnershipGraph, OwnershipNode
from tools.groq_client import call_groq

_SYSTEM = (
    "You extract corporate ownership structures from company filings "
    "(MGT-7, shareholding patterns) or analyst-written descriptions. "
    "You will be given the vendor name and some source text. "
    "Return a JSON object representing the ownership tree, where "
    "`vendor_root` is the vendor and `children` are its DIRECT shareholders. "
    "Each child may have its own children (recursive, one layer up). "
    "Fields on each node:\n"
    "  name: entity or person name as written in the source\n"
    "  stake_pct: percentage this node holds in its parent (0-100, or null "
    "if unclear). Root (vendor) has stake_pct null.\n"
    "  entity_type: one of 'natural_person' | 'company' | 'llp' | 'trust' "
    "| 'huf' | 'listed' | 'government' | 'foreign_entity' | 'unknown'. "
    "If the shareholder is a person, 'natural_person'. If a company is "
    "incorporated outside India, 'foreign_entity'. 'listed' only if "
    "explicitly stated as publicly listed.\n"
    "  jurisdiction: country name (e.g. 'India', 'Singapore', 'USA'), or "
    "null if the source doesn't say.\n"
    "  children: list, empty if no further ownership is given.\n"
    "  note: short clarifying note if anything is ambiguous (e.g. 'stake "
    "unclear, source lists only name').\n\n"
    "Important handling rules:\n"
    "- Do NOT invent shareholders not mentioned in the source.\n"
    "- If the source clearly contains ownership data but the company name "
    "in the source differs from the vendor name, EXTRACT the ownership "
    "anyway and add a `note` on vendor_root saying something like 'Source "
    "names X; verify this filing belongs to the stated vendor'. Do not "
    "refuse to extract — the analyst can confirm or reject the filing.\n"
    "- If the source is genuinely empty / unparseable / contains no "
    "ownership data at all, return a root with no children and a `note` "
    "explaining why.\n\n"
    "Return ONLY the JSON object. No markdown fences, no prose outside JSON."
)


def extract_ownership_graph(
    vendor_name: str, source_text: str, source_label: str, groq_api_keys: list[str]
) -> OwnershipGraph:
    """
    source_text can be the concatenation of multiple LlamaParse outputs
    plus any analyst-typed description — the model treats it as one blob.
    source_label is for provenance ('document:MGT7.pdf+MGT9.pdf' or
    'analyst-text' or 'combined').
    """
    user_prompt = (
        f"Vendor: {vendor_name}\n\n"
        f"Source text:\n---\n{source_text[:14000]}\n---\n\n"
        f"Extract the ownership tree. Return JSON only."
    )
    try:
        raw = call_groq(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            api_keys=groq_api_keys,
            max_tokens=2000,
        ).strip()
    except Exception as exc:
        return OwnershipGraph(
            vendor_root=OwnershipNode(
                name=vendor_name,
                entity_type="unknown",
                note=f"Extraction failed: {exc}. Please edit this graph manually.",
            ),
            raw_source=source_label,
        )

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return OwnershipGraph(
            vendor_root=OwnershipNode(
                name=vendor_name, entity_type="unknown",
                note="Model returned no JSON object. Edit this graph manually.",
            ),
            raw_source=source_label,
        )

    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        return OwnershipGraph(
            vendor_root=OwnershipNode(
                name=vendor_name, entity_type="unknown",
                note=f"Model returned invalid JSON ({exc}). Edit manually.",
            ),
            raw_source=source_label,
        )

    root_payload = payload.get("vendor_root") if isinstance(payload, dict) else None
    if root_payload is None:
        root_payload = payload
    root_payload = _coerce_root(root_payload, vendor_name)
    _normalize_node(root_payload)
    try:
        root = OwnershipNode.model_validate(root_payload)
    except Exception as exc:
        return OwnershipGraph(
            vendor_root=OwnershipNode(
                name=vendor_name, entity_type="unknown",
                note=f"Model output failed schema validation: {exc}. Edit manually.",
            ),
            raw_source=source_label,
        )

    return OwnershipGraph(vendor_root=root, raw_source=source_label)


def _coerce_root(root_payload, vendor_name: str) -> dict:
    """
    Ensure the root is a dict shaped like OwnershipNode. The model
    occasionally returns:
    - a bare string (just the vendor name)
    - a list (the shareholders directly, no wrapping root)
    - a dict with no `name` field
    All of these get coerced here instead of crashing validation.
    """
    if isinstance(root_payload, str):
        return {"name": root_payload or vendor_name, "entity_type": "unknown", "children": []}
    if isinstance(root_payload, list):
        return {"name": vendor_name, "entity_type": "unknown", "children": root_payload}
    if not isinstance(root_payload, dict):
        return {"name": vendor_name, "entity_type": "unknown", "children": []}
    if not root_payload.get("name"):
        root_payload["name"] = vendor_name
    return root_payload


def _normalize_node(node) -> None:
    """
    gpt-oss occasionally emits a child as a bare string instead of a node
    object, or wraps `children` in something that isn't a list. Walk the
    tree in place and coerce those shapes into valid OwnershipNode dicts so
    pydantic validation succeeds.
    """
    if not isinstance(node, dict):
        return
    # Ensure name exists on every node — the schema requires it.
    if not node.get("name"):
        node["name"] = "Unknown"
    kids = node.get("children")
    if kids is None:
        node["children"] = []
        return
    if isinstance(kids, str):
        kids = [kids]
    if not isinstance(kids, list):
        node["children"] = []
        return
    coerced: list = []
    for k in kids:
        if isinstance(k, dict):
            _normalize_node(k)
            coerced.append(k)
        elif isinstance(k, str):
            # Model dropped a bare name — wrap it as an unknown-type stub so
            # the analyst at least sees the name and can edit the rest.
            coerced.append({"name": k, "entity_type": "unknown", "children": []})
        # Anything else (int, None, nested list) — skip silently.
    node["children"] = coerced
