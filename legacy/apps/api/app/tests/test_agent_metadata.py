"""Agent metadata covers every agent in the registry."""
from __future__ import annotations

from app.agents.registry import AGENTS
from app.services.agent_metadata import AGENT_METADATA, list_metadata


def test_every_registered_agent_has_metadata():
    missing = set(AGENTS.keys()) - set(AGENT_METADATA.keys())
    assert not missing, f"agents without metadata: {missing}"


def test_every_metadata_has_required_fields():
    for name, m in AGENT_METADATA.items():
        # angle is the one universal required field
        assert any(f.key == "angle" and f.required for f in m.fields), f"{name} missing required angle field"
        assert m.default_platform
        assert m.default_content_type
        assert m.group


def test_list_metadata_is_grouped_in_canonical_order():
    seen_groups = []
    for item in list_metadata():
        if item["group"] not in seen_groups:
            seen_groups.append(item["group"])
    # the order should be exactly the GROUP_ORDER constant, filtered to present groups
    from app.services.agent_metadata import GROUP_ORDER
    expected = [g for g in GROUP_ORDER if any(m.group == g for m in AGENT_METADATA.values())]
    assert seen_groups == expected
