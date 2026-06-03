"""Every claimed agent is registered with a real class (no aliases)."""
from __future__ import annotations

import inspect

from app.agents.registry import AGENTS


EXPECTED = {
    "static_post", "carousel", "blog", "email",
    "short_video", "long_video", "reel_voice",
    "thread_post", "ads",
}


def test_every_expected_agent_present():
    missing = EXPECTED - set(AGENTS.keys())
    assert not missing, f"missing agents: {missing}"


def test_no_aliasing_duplicates():
    # each agent class should appear exactly once
    classes = list(AGENTS.values())
    assert len(set(classes)) == len(classes), f"alias duplicate detected: {classes}"


def test_every_agent_has_run_method():
    for name, cls in AGENTS.items():
        assert hasattr(cls, "run"), f"{name} has no run()"
        assert callable(getattr(cls, "run")), f"{name}.run not callable"


def test_every_agent_has_name_attr():
    for name, cls in AGENTS.items():
        instance_name = getattr(cls, "name", None)
        assert instance_name == name, f"{cls.__name__}.name={instance_name!r} but registered as {name!r}"
