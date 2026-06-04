"""Per-request override plumbing — parse, max_tokens, tier, prompt-merge."""
from __future__ import annotations

import json

from app.agents._overrides import Overrides, apply_to_system, max_tokens_for, parse, tier_for


def test_parse_returns_blank_overrides_when_no_marker():
    assert parse("just a reason").tone is None
    assert parse(None).length is None
    assert parse("").model is None


def test_parse_extracts_json_after_pipe():
    raw = 'ad-hoc create by hi@x.com | ' + json.dumps({"tone": "punchy", "length": "short"})
    ov = parse(raw)
    assert ov.tone == "punchy"
    assert ov.length == "short"


def test_max_tokens_scales():
    assert max_tokens_for(1000, "short") == 500
    assert max_tokens_for(1000, "long") == 2000
    assert max_tokens_for(1000, None) == 1000
    assert max_tokens_for(1000, "medium") == 1000


def test_tier_for_override():
    from app.pipeline.llm_gateway import LLMTier
    assert tier_for(LLMTier.DRAFTING, "reasoning") == LLMTier.REASONING
    assert tier_for(LLMTier.REASONING, "drafting") == LLMTier.DRAFTING
    assert tier_for(LLMTier.DRAFTING, "auto") == LLMTier.DRAFTING
    assert tier_for(LLMTier.DRAFTING, None) == LLMTier.DRAFTING


def test_apply_to_system_no_op_when_blank():
    assert apply_to_system("base", Overrides()) == "base"


def test_apply_to_system_appends_tone_and_custom():
    out = apply_to_system("base", Overrides(tone="sceptical", custom_instructions="End with a poll."))
    assert "sceptical" in out
    assert "End with a poll." in out
    assert out.startswith("base")
