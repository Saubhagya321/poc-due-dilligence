"""
The LLM returns sloppy shapes often enough that we need defensive coercion
before pydantic validation. Instead of mocking Groq, these tests exercise
`_coerce_root` and `_normalize_node` directly on the exact bad shapes
we've seen in production: bare-string root, bare-string children, missing
`name` field, non-list `children`.
"""
from agents.ubo_extractor import _coerce_root, _normalize_node
from schemas.ubo import OwnershipNode


def test_bare_string_root_is_wrapped_into_a_stub_node():
    coerced = _coerce_root("Gitanjali Gems Limited", "Gitanjali Gems Limited")
    _normalize_node(coerced)
    node = OwnershipNode.model_validate(coerced)

    assert node.name == "Gitanjali Gems Limited"
    assert node.entity_type == "unknown"
    assert node.children == []


def test_root_payload_as_list_wraps_in_stub_root_with_vendor_name():
    children_payload = [
        {"name": "Mehul Choksi", "stake_pct": 70, "entity_type": "natural_person"},
        {"name": "Priti Choksi", "stake_pct": 30, "entity_type": "natural_person"},
    ]
    coerced = _coerce_root(children_payload, "Vendor Co")
    _normalize_node(coerced)
    node = OwnershipNode.model_validate(coerced)

    assert node.name == "Vendor Co"
    assert len(node.children) == 2
    assert node.children[0].name == "Mehul Choksi"


def test_bare_string_child_is_coerced_into_a_stub_node():
    payload = {
        "name": "Acme Pvt Ltd",
        "children": ["John Doe", {"name": "Jane Doe", "stake_pct": 40}],
    }
    _normalize_node(payload)
    node = OwnershipNode.model_validate(payload)

    assert len(node.children) == 2
    assert node.children[0].name == "John Doe"
    assert node.children[0].entity_type == "unknown"
    assert node.children[1].name == "Jane Doe"


def test_missing_name_on_a_node_gets_a_placeholder():
    payload = {"children": [{"stake_pct": 50}]}  # no name on root or child
    coerced = _coerce_root(payload, "Vendor X")
    _normalize_node(coerced)
    node = OwnershipNode.model_validate(coerced)

    assert node.name == "Vendor X"  # from vendor_name fallback
    assert node.children[0].name == "Unknown"  # placeholder


def test_children_as_single_string_becomes_a_one_item_list():
    payload = {"name": "Acme", "children": "John Doe"}
    _normalize_node(payload)
    node = OwnershipNode.model_validate(payload)

    assert len(node.children) == 1
    assert node.children[0].name == "John Doe"


def test_a_well_formed_payload_round_trips_unchanged():
    payload = {
        "name": "Micron India LLP",
        "stake_pct": None,
        "entity_type": "llp",
        "jurisdiction": "India",
        "children": [
            {
                "name": "Micron Technology Inc",
                "stake_pct": 99.9,
                "entity_type": "foreign_entity",
                "jurisdiction": "USA",
                "children": [],
            }
        ],
    }
    _normalize_node(payload)
    node = OwnershipNode.model_validate(payload)

    assert node.name == "Micron India LLP"
    assert node.children[0].name == "Micron Technology Inc"
    assert node.children[0].jurisdiction == "USA"
