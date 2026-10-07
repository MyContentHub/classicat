"""分类逻辑层：评级校验 → FIPS 199 高水位线 → 标签映射 → 复核标记（纯函数）。"""

LEVEL_ORDER = ["public", "internal", "restricted", "confidential"]
RATING_ORDER = {"low": 0, "moderate": 1, "high": 2}
DIMENSIONS = ("c", "i", "a")


def resolve(analysis: dict, catalog: dict, rules: dict) -> dict:
    """LLM 分析结果 → 最终标签。

    目录内类型：每维取 max(门控后 LLM 评级, 目录基线)——下调一律回落基线，
    上调需 confidence 达标且 evidence 非空；未知类型按 LLM 评级并标记待归类。
    SC 逐维取所有类型最大值，查 level_rules 得标签；全部类型带 public 标记 → public。
    """
    review_confidence = rules["review_confidence"]
    try:
        confidence = float(analysis.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    reported = analysis.get("information_types")
    if not isinstance(reported, list):
        reported = []

    dims = {d: "low" for d in DIMENSIONS}
    unmapped = []
    all_public = bool(reported)
    for item in reported:
        if not isinstance(item, dict):
            item = {}
        name = str(item.get("type", ""))
        baseline = catalog.get(name)
        can_upgrade = confidence >= review_confidence and bool(str(item.get("evidence") or "").strip())
        if baseline is None:
            unmapped.append(name)
            all_public = False
            for d in DIMENSIONS:
                rating = item.get(d) if item.get(d) in RATING_ORDER else "moderate"
                if RATING_ORDER[rating] > RATING_ORDER[dims[d]]:
                    dims[d] = rating
        else:
            all_public = all_public and bool(baseline.get("public"))
            for d in DIMENSIONS:
                value = baseline[d]
                rating = item.get(d)
                if rating in RATING_ORDER and RATING_ORDER[rating] > RATING_ORDER[value] and can_upgrade:
                    value = rating
                if RATING_ORDER[value] > RATING_ORDER[dims[d]]:
                    dims[d] = value

    if all_public:
        label = "public"
    else:
        label = rules["level_rules"][max(dims.values(), key=RATING_ORDER.get)]

    reasons = []
    if not reported:
        reasons.append("no information types reported")
    if confidence < review_confidence:
        reasons.append(f"confidence {confidence:.2f} < {review_confidence}")
    if unmapped:
        reasons.append("unmapped types: " + ", ".join(unmapped))

    direction = ""
    suggested = analysis.get("suggested_label")
    if suggested in LEVEL_ORDER and suggested != label:
        direction = "over" if LEVEL_ORDER.index(label) > LEVEL_ORDER.index(suggested) else "under"
        reasons.append(f"suggested {suggested} but resolved {label} ({direction})")

    return {
        "category_matched": label,
        "security_category": dims,
        "needs_review": bool(reasons),
        "review_reasons": reasons,
        "unmapped_types": unmapped,
        "review_direction": direction,
    }
