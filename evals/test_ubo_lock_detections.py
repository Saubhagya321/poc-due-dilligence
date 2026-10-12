"""
Structural red-flag detectors in ubo_lock. Each test builds the smallest
graph that should trip one specific detector and asserts the tag + a
substring of the reason.
"""
from agents.ubo_lock import _tag_for_graph, _walk_nodes
from schemas.evidence import FindingTag
from schemas.ubo import OwnershipNode


def _tag(root: OwnershipNode) -> tuple[FindingTag, str]:
    return _tag_for_graph(root, _walk_nodes(root))


def test_clean_graph_with_only_indian_natural_persons_is_green():
    root = OwnershipNode(
        name="Acme Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(name="Alice", stake_pct=60, entity_type="natural_person", jurisdiction="India"),
            OwnershipNode(name="Bob", stake_pct=40, entity_type="natural_person", jurisdiction="India"),
        ],
    )
    tag, _ = _tag(root)
    assert tag == FindingTag.RESOLVED_CLEAN


def test_cyclic_ownership_is_red_flagged_as_round_tripping():
    # Acme owns Beta owns Acme (cycle via name repetition on a path)
    root = OwnershipNode(
        name="Acme Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(
                name="Beta Holdings", stake_pct=100, entity_type="company", jurisdiction="India",
                children=[OwnershipNode(name="Acme Pvt Ltd", stake_pct=100, entity_type="company", jurisdiction="India")],
            )
        ],
    )
    tag, reason = _tag(root)
    assert tag == FindingTag.RESOLVED_RED_FLAG
    assert "round-tripping" in reason.lower() or "cyclic" in reason.lower()


def test_two_consecutive_foreign_nodes_is_red_shell_structure():
    root = OwnershipNode(
        name="Vendor Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(
                name="Mauritius Holdings", stake_pct=100, entity_type="foreign_entity", jurisdiction="Mauritius",
                children=[
                    OwnershipNode(name="BVI Shell Co", stake_pct=100, entity_type="foreign_entity", jurisdiction="BVI"),
                ],
            )
        ],
    )
    tag, reason = _tag(root)
    assert tag == FindingTag.RESOLVED_RED_FLAG
    assert "shell" in reason.lower() or "foreign" in reason.lower()


def test_single_foreign_node_stays_amber_not_red():
    root = OwnershipNode(
        name="Vendor Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(name="Singapore Parent Pte", stake_pct=60, entity_type="foreign_entity", jurisdiction="Singapore"),
            OwnershipNode(name="Rajesh", stake_pct=40, entity_type="natural_person", jurisdiction="India"),
        ],
    )
    tag, reason = _tag(root)
    assert tag == FindingTag.UNRESOLVED
    assert "foreign" in reason.lower()


def test_three_shareholders_in_sbo_fragmentation_range_is_amber():
    root = OwnershipNode(
        name="Vendor Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(name="A", stake_pct=9.5, entity_type="natural_person", jurisdiction="India"),
            OwnershipNode(name="B", stake_pct=9.0, entity_type="natural_person", jurisdiction="India"),
            OwnershipNode(name="C", stake_pct=8.5, entity_type="natural_person", jurisdiction="India"),
            OwnershipNode(name="D", stake_pct=73.0, entity_type="natural_person", jurisdiction="India"),
        ],
    )
    tag, reason = _tag(root)
    assert tag == FindingTag.UNRESOLVED
    assert "sbo" in reason.lower() or "fragment" in reason.lower() or "disclosure" in reason.lower()


def test_two_sub_threshold_shareholders_is_not_enough_to_flag():
    root = OwnershipNode(
        name="Vendor Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(name="A", stake_pct=9.0, entity_type="natural_person", jurisdiction="India"),
            OwnershipNode(name="B", stake_pct=9.0, entity_type="natural_person", jurisdiction="India"),
            OwnershipNode(name="C", stake_pct=82.0, entity_type="natural_person", jurisdiction="India"),
        ],
    )
    tag, _ = _tag(root)
    assert tag == FindingTag.RESOLVED_CLEAN


def test_nominee_mention_in_a_node_note_is_amber():
    root = OwnershipNode(
        name="Vendor Pvt Ltd", entity_type="company", jurisdiction="India",
        children=[
            OwnershipNode(
                name="Family Member", stake_pct=60, entity_type="natural_person",
                jurisdiction="India", note="Likely holding as nominee for the real owner",
            ),
            OwnershipNode(name="Other", stake_pct=40, entity_type="natural_person", jurisdiction="India"),
        ],
    )
    tag, reason = _tag(root)
    assert tag == FindingTag.UNRESOLVED
    assert "nominee" in reason.lower() or "benami" in reason.lower() or "proxy" in reason.lower()


def test_empty_graph_is_amber_with_shareholders_prompt():
    root = OwnershipNode(name="Vendor Pvt Ltd", entity_type="company", jurisdiction="India", children=[])
    tag, reason = _tag(root)
    assert tag == FindingTag.UNRESOLVED
    assert "no shareholders" in reason.lower()
