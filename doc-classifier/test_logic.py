"""logic.py 高水位线与复核规则自检（纯函数，不调 LLM）。"""

from logic import resolve


RULES = {
    "review_confidence": 0.7,
    "level_rules": {"high": "confidential", "moderate": "restricted", "low": "internal"},
    "information_types": {
        "员工客户PII": {"c": "high", "i": "moderate", "a": "low"},
        "会议纪要制度": {"c": "moderate", "i": "low", "a": "low"},
        "公开发布信息": {"c": "low", "i": "low", "a": "low", "public": True},
    },
}


def analysis(types, suggested="internal", confidence=0.9):
    return {"information_types": types, "suggested_label": suggested, "confidence": confidence}


def pii(**overrides):
    item = {"type": "员工客户PII", "c": "high", "i": "moderate", "a": "low", "evidence": "id numbers"}
    item.update(overrides)
    return item


def test_high_water_mark():
    types = [pii(), {"type": "会议纪要制度", "c": "low", "i": "low", "a": "low", "evidence": "minutes"}]
    result = resolve(analysis(types, suggested="confidential"), RULES["information_types"], RULES)
    assert result["category_matched"] == "confidential"
    assert result["security_category"] == {"c": "high", "i": "moderate", "a": "low"}
    assert not result["needs_review"]


def test_baseline_floor_downgrade_ignored():
    result = resolve(analysis([pii(c="low", i="low")], suggested="internal"), RULES["information_types"], RULES)
    assert result["category_matched"] == "confidential"


def test_upgrade_requires_evidence_and_confidence():
    proposal = {"type": "会议纪要制度", "c": "high", "i": "low", "a": "low"}
    no_evidence = resolve(analysis([proposal], confidence=0.95), RULES["information_types"], RULES)
    assert no_evidence["category_matched"] == "restricted"  # 回落基线 moderate

    gated = resolve(analysis([{**proposal, "evidence": "secret spec"}], confidence=0.5), RULES["information_types"], RULES)
    assert gated["category_matched"] == "restricted"
    assert gated["needs_review"]  # 低置信度

    upgraded = resolve(analysis([{**proposal, "evidence": "secret spec"}]), RULES["information_types"], RULES)
    assert upgraded["category_matched"] == "confidential"  # 上调生效，high → confidential


def test_unmapped_type_uses_llm_rating_and_marks_review():
    unknown = {"type": "客户合同条款", "c": "high", "i": "low", "a": "low", "evidence": "contract"}
    result = resolve(analysis([unknown], suggested="restricted"), RULES["information_types"], RULES)
    assert result["category_matched"] == "confidential"
    assert result["unmapped_types"] == ["客户合同条款"]
    assert result["needs_review"] and any("unmapped" in r for r in result["review_reasons"])


def test_public_flag_maps_to_public():
    item = {"type": "公开发布信息", "c": "low", "i": "low", "a": "low", "evidence": "press release"}
    result = resolve(analysis([item], suggested="public"), RULES["information_types"], RULES)
    assert result["category_matched"] == "public"
    assert not result["needs_review"]


def test_direction_marks_over_and_under():
    over = resolve(analysis([pii()], suggested="internal"), RULES["information_types"], RULES)
    assert over["review_direction"] == "over" and over["needs_review"]

    public_item = {"type": "公开发布信息", "c": "low", "i": "low", "a": "low", "evidence": "x"}
    under = resolve(analysis([public_item], suggested="confidential"), RULES["information_types"], RULES)
    assert under["review_direction"] == "under" and under["needs_review"]


def test_no_types_needs_review():
    result = resolve(analysis([], suggested="public"), RULES["information_types"], RULES)
    assert result["category_matched"] == "internal"  # low 水位线兜底
    assert result["needs_review"]
