"""
Converts a locked OwnershipGraph into evidence records: one OWNERSHIP_BEHAVIOUR
record representing the UBO trace itself, plus one OpenSanctions record per
natural-person UBO so sanctions screening + hard-override still fire.
"""
from datetime import date

from schemas.evidence import (
    CheckStatus,
    ConfidenceTier,
    EvidenceRecord,
    FindingCategory,
    FindingTag,
    SupportingCitation,
)
from schemas.ubo import OwnershipGraph, OwnershipNode
from tools.opensanctions import sanctions_pep_screen

UBO_SOURCE_NAME = "Analyst UBO trace"
UBO_SOURCE_REFERENCE = "ubo_trace"


_NOMINEE_KEYWORDS = ("nominee", "benamidar", "benami", "proxy", "on behalf of")


def _walk_nodes(root: OwnershipNode) -> list[OwnershipNode]:
    """Depth-first flatten of every node in the ownership tree, including the root."""
    out = [root]
    for child in root.children:
        out.extend(_walk_nodes(child))
    return out


def _all_paths(root: OwnershipNode, prefix: list[str] | None = None) -> list[list[str]]:
    """Every root-to-leaf path, as a list of lowercased node names."""
    prefix = (prefix or []) + [root.name.strip().lower()]
    if not root.children:
        return [prefix]
    paths: list[list[str]] = []
    for child in root.children:
        paths.extend(_all_paths(child, prefix))
    return paths


def _detect_cycle(root: OwnershipNode) -> list[list[str]]:
    """Any root-to-leaf path where a name appears twice is a round-tripping signal."""
    cycles: list[list[str]] = []
    for path in _all_paths(root):
        if len(path) != len(set(path)):
            cycles.append(path)
    return cycles


def _detect_deep_foreign_chain(root: OwnershipNode) -> list[list[str]]:
    """
    Flag paths with 2+ consecutive foreign-jurisdiction nodes — classic
    opaque-shell-layering (vendor → Singapore co → BVI co → Cayman trust).
    """
    def _is_foreign(n: OwnershipNode) -> bool:
        if n.entity_type == "foreign_entity":
            return True
        if n.jurisdiction and n.jurisdiction.strip().lower() not in {"india", "", "unknown"}:
            return True
        return False

    def _walk(node: OwnershipNode, chain: list[str]) -> list[list[str]]:
        hits: list[list[str]] = []
        for child in node.children:
            if _is_foreign(child):
                new_chain = chain + [child.name]
                if len(new_chain) >= 2:
                    hits.append(new_chain)
                hits.extend(_walk(child, new_chain))
            else:
                hits.extend(_walk(child, []))
        return hits

    return _walk(root, [])


def _detect_sbo_fragmentation(root: OwnershipNode) -> list[OwnershipNode]:
    """
    Shareholders held just below the 10% SBO disclosure threshold (7-9.99%) in
    quantity — classic trick to split one person's stake across family / cousins
    / trusts so nobody individually crosses 10%.
    """
    at_risk = [
        n for n in root.children
        if n.stake_pct is not None and 7.0 <= n.stake_pct < 10.0
    ]
    return at_risk if len(at_risk) >= 3 else []


def _detect_nominee_flags(all_nodes: list[OwnershipNode]) -> list[OwnershipNode]:
    """Any node whose note mentions nominee/benami/proxy terminology."""
    flagged: list[OwnershipNode] = []
    for node in all_nodes:
        hay = (node.note or "").lower()
        if any(kw in hay for kw in _NOMINEE_KEYWORDS):
            flagged.append(node)
    return flagged


def _tag_for_graph(root: OwnershipNode, all_nodes: list[OwnershipNode]) -> tuple[FindingTag, str]:
    """
    Worst-signal-wins tag for the UBO tile. Red overrides amber overrides clean.

    RED signals (structural fraud markers):
      - Cyclic ownership (round-tripping)
      - 2+ consecutive foreign nodes (opaque shell layering)

    AMBER signals (needs human review):
      - Any single foreign-jurisdiction node
      - Trust / HUF / unknown entity type (needs more tracing)
      - 3+ shareholders held in the 7-9.99% range (SBO fragmentation)
      - Any nominee / benami / proxy mention in notes
      - No shareholders identified at all

    CLEAN: every non-root node is an Indian natural_person / listed / government,
    none of the structural flags triggered.
    """
    non_root = all_nodes[1:]
    red_reasons: list[str] = []
    amber_reasons: list[str] = []

    cycles = _detect_cycle(root)
    if cycles:
        red_reasons.append(
            f"Cyclic ownership detected (round-tripping / self-reference): {len(cycles)} path(s), e.g. "
            + " → ".join(cycles[0])
        )

    deep_foreign = _detect_deep_foreign_chain(root)
    if deep_foreign:
        red_reasons.append(
            f"Opaque multi-layer foreign shell structure: {len(deep_foreign)} chain(s) with 2+ consecutive foreign-jurisdiction nodes, e.g. "
            + " → ".join(deep_foreign[0])
        )

    foreign = [
        n for n in non_root
        if n.entity_type == "foreign_entity"
        or (n.jurisdiction and n.jurisdiction.strip().lower() not in {"india", ""})
    ]
    needs_more = [n for n in non_root if n.entity_type in {"trust", "huf", "unknown"}]
    nominee_hits = _detect_nominee_flags(all_nodes)
    sbo_fragmented = _detect_sbo_fragmentation(root)

    if foreign and not deep_foreign:  # already captured in the red reason above
        amber_reasons.append(
            f"{len(foreign)} shareholder(s) in foreign jurisdictions — never treated as fully clean per spec: "
            + ", ".join(f"{n.name} ({n.jurisdiction or 'unknown'})" for n in foreign[:5])
        )
    if needs_more:
        amber_reasons.append(
            f"{len(needs_more)} node(s) need further tracing (trust / HUF / unknown): "
            + ", ".join(n.name for n in needs_more[:5])
        )
    if nominee_hits:
        amber_reasons.append(
            f"{len(nominee_hits)} node(s) flagged as nominee / benami / proxy: "
            + ", ".join(n.name for n in nominee_hits[:5])
        )
    if sbo_fragmented:
        amber_reasons.append(
            f"Possible SBO-threshold evasion: {len(sbo_fragmented)} shareholders held at 7-9.99% stake (just below the 10% disclosure threshold) — "
            + ", ".join(f"{n.name} ({n.stake_pct}%)" for n in sbo_fragmented[:5])
        )

    if red_reasons:
        return FindingTag.RESOLVED_RED_FLAG, " | ".join(red_reasons + amber_reasons)
    if amber_reasons:
        return FindingTag.UNRESOLVED, " | ".join(amber_reasons)
    if len(non_root) == 0:
        return FindingTag.UNRESOLVED, "No shareholders identified in the graph — upload a shareholding filing or add shareholders manually."
    return FindingTag.RESOLVED_CLEAN, (
        f"All {len(non_root)} shareholder(s) identified are Indian natural persons / listed / "
        "government entities, no cyclic / shell / nominee / fragmentation flags detected."
    )


def _node_citations(all_nodes: list[OwnershipNode]) -> list[SupportingCitation]:
    """Each identified shareholder (not the vendor root) becomes a supporting citation on the UBO record."""
    cites = []
    for node in all_nodes[1:]:
        stake = f"{node.stake_pct:.2f}%" if node.stake_pct is not None else "stake unclear"
        label = f"{node.name} — {stake}, {node.entity_type}, {node.jurisdiction or 'jurisdiction unknown'}"
        if node.note:
            label += f" ({node.note})"
        cites.append(
            SupportingCitation(
                title=label,
                url="ubo-graph://" + node.name.replace(" ", "_"),
                source="UBO graph",
            )
        )
    return cites


def ubo_graph_to_records(
    vendor_id: str, graph: OwnershipGraph, opensanctions_api_key: str
) -> list[EvidenceRecord]:
    """
    Returns:
      1 OWNERSHIP_BEHAVIOUR record capturing the whole graph (always), plus
      0..N GLOBAL_COMPLIANCE OpenSanctions records (one per natural-person
      UBO) so the sanctions hard-override fires if any UBO is sanctioned.
    """
    all_nodes = _walk_nodes(graph.vendor_root)
    tag, summary = _tag_for_graph(graph.vendor_root, all_nodes)

    ubo_record = EvidenceRecord(
        vendor_id=vendor_id,
        category=FindingCategory.OWNERSHIP_BEHAVIOUR,
        source_name=UBO_SOURCE_NAME,
        source_reference=UBO_SOURCE_REFERENCE,
        summary=summary + (f" | Analyst notes: {graph.analyst_notes}" if graph.analyst_notes else ""),
        tag=tag,
        confidence_tier=ConfidenceTier.TIER_3,
        as_of_date=date.today(),
        check_status=CheckStatus.AMBIGUOUS_MATCH if tag == FindingTag.UNRESOLVED else CheckStatus.SUCCESS,
        citation_url=f"ubo-graph://{vendor_id}",
        supporting_citations=_node_citations(all_nodes),
    )

    records: list[EvidenceRecord] = [ubo_record]

    # Fire sanctions screen on every natural-person node so a sanctioned UBO
    # still triggers the hard-override via the existing GLOBAL_COMPLIANCE path.
    for node in all_nodes[1:]:
        if node.entity_type != "natural_person":
            continue
        try:
            rec = sanctions_pep_screen(
                vendor_id=vendor_id, name=node.name, pan=None, api_key=opensanctions_api_key
            )
            # Only forward RED/AMBER — a clean per-UBO sanctions result adds
            # noise to the sanctions tile without new information.
            if rec.tag in (FindingTag.RESOLVED_RED_FLAG, FindingTag.UNRESOLVED):
                records.append(rec)
        except Exception:
            continue  # UBO screening failure shouldn't block the lock

    return records
