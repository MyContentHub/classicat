"""doc-classifier 基准测试：社区集测 PII 召回，自建集测分级边界。

用法：
    uv run eval/run_eval.py --mode levels   # 自建 20 个中文样本，测四级分级
    uv run eval/run_eval.py --mode pii      # ai4privacy OpenPII 验证集抽样（中英各半），测 PII 召回（需 dev 依赖 datasets）
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

import yaml
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parents[1]))

from main import classify_content
from main import apply_env_overrides

LEVELS = ["public", "internal", "restricted", "confidential"]
EVAL_DIR = Path(__file__).parent


def classify_text(client: OpenAI, config: dict, text: str) -> str:
    return classify_content(client, config, text)["category_matched"]


def run_levels(client: OpenAI, config: dict) -> list[dict]:
    """自建样本集：文件名前缀即标准答案。"""
    rows = []
    for path in sorted((EVAL_DIR / "eval_samples").glob("*.md")):
        expected = path.name.split("__")[0]
        try:
            predicted = classify_text(client, config, path.read_text(encoding="utf-8"))
            error = ""
        except Exception as e:
            predicted, error = "", str(e)
        rows.append({"mode": "levels", "file": path.name, "expected": expected, "predicted": predicted, "error": error})
    return rows


def run_pii(client: OpenAI, config: dict, n_per_class: int) -> list[dict]:
    """ai4privacy OpenPII 验证集抽样：source_text=含 PII（阳性），masked_text=脱敏后（阴性）。"""
    sample = build_sample(n_per_class)

    rows = []
    for label, texts in (("pii", sample["positive"]), ("clean", sample["negative"])):
        for i, text in enumerate(texts):
            try:
                predicted = classify_text(client, config, text)
                error = ""
            except Exception as e:
                predicted, error = "", str(e)
            rows.append({"mode": "pii", "file": f"{label}#{i}", "expected": label, "predicted": predicted, "error": error})
    return rows


def build_sample(n_per_class: int) -> dict:
    """从 OpenPII 验证集抽阳性样本（含 PII 原文，中英各半）。

    阴性样本全部使用自建真干净文本（public/internal）：OpenPII 的无 PII 行
    仍是占位符模板文本，会导致负样本污染（模型判其含 PII 是合理的）。
    结果缓存到本地 JSON，固定随机种子，保证多次运行样本一致。
    """
    cache = EVAL_DIR / "pii_cache" / "sample.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    from datasets import load_dataset

    ds = load_dataset("ai4privacy/pii-masking-openpii-1.5m", split="validation")
    zh = [r for r in ds if r["language"] == "zh"]
    en = [r for r in ds if r["language"] == "en"]
    pos_zh = [r["source_text"] for r in zh if r["privacy_mask"]]
    pos_en = [r["source_text"] for r in en if r["privacy_mask"]]
    built_in = [
        p.read_text(encoding="utf-8")
        for p in sorted((EVAL_DIR / "eval_samples").glob("*.md"))
        if p.name.split("__")[0] in ("public", "internal")
    ]
    neg_pool = built_in
    for name, pool, floor in (("pos-zh", pos_zh, n_per_class), ("pos-en", pos_en, n_per_class), ("neg", neg_pool, 20)):
        if len(pool) < floor:
            raise ValueError(f"OpenPII/自建集 has too few {name} samples: {len(pool)} (need {floor})")
    rng = random.Random(42)
    half = n_per_class // 2
    sample = {
        "positive": rng.sample(pos_zh, half) + rng.sample(pos_en, n_per_class - half),
        "negative": list(neg_pool),  # 自建真干净样本全量使用，不抽样
    }
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    return sample


def report_levels(rows: list[dict]) -> str:
    """混淆矩阵 + 每级准确率 + 不足/过度分类率。"""
    valid = [r for r in rows if not r["error"]]
    lines = ["== levels benchmark ==", "expected\\pred".ljust(16) + "".join(l.ljust(16) for l in LEVELS)]
    for expected in LEVELS:
        counts = Counter(r["predicted"] for r in valid if r["expected"] == expected)
        lines.append(expected.ljust(16) + "".join(str(counts.get(l, 0)).ljust(16) for l in LEVELS))
    n = len(valid)
    if n:
        correct = sum(1 for r in valid if r["predicted"] == r["expected"])
        under = sum(1 for r in valid if r["predicted"] in LEVELS and LEVELS.index(r["predicted"]) < LEVELS.index(r["expected"]))
        over = sum(1 for r in valid if r["predicted"] in LEVELS and LEVELS.index(r["predicted"]) > LEVELS.index(r["expected"]))
        lines += [
            f"accuracy: {correct}/{n} = {correct / n:.1%}",
            f"under-classification (安全风险): {under}/{n} = {under / n:.1%}",
            f"over-classification: {over}/{n} = {over / n:.1%}",
        ]
    return "\n".join(lines)


def report_pii(rows: list[dict]) -> str:
    """PII 二元视角：predicted == 'confidential' 视为阳性。"""
    valid = [r for r in rows if not r["error"]]
    tp = sum(1 for r in valid if r["expected"] == "pii" and r["predicted"] == "confidential")
    fn = sum(1 for r in valid if r["expected"] == "pii" and r["predicted"] != "confidential")
    fp = sum(1 for r in valid if r["expected"] == "clean" and r["predicted"] == "confidential")
    tn = sum(1 for r in valid if r["expected"] == "clean" and r["predicted"] != "confidential")
    lines = ["== pii benchmark =="]
    if tp + fn:
        lines.append(f"recall (PII 被判为机密): {tp}/{tp + fn} = {tp / (tp + fn):.1%}")
    if fp + tn:
        lines.append(f"false positive rate (干净文本被判机密): {fp}/{fp + tn} = {fp / (fp + tn):.1%}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="doc-classifier benchmark")
    parser.add_argument("--mode", choices=["levels", "pii"], default="levels")
    parser.add_argument("--config", type=Path, default=Path(__file__).parents[1] / "config.yaml")
    parser.add_argument("--n", type=int, default=100, help="pii 模式每类抽样条数")
    parser.add_argument("--output", type=Path, default=None, help="默认 eval_report_<mode>.csv")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    apply_env_overrides(config, Path(__file__).parents[1] / ".env")
    client = OpenAI(base_url=config["llm_server"]["base_url"], api_key=config["llm_server"].get("api_key", "ollama"))
    rows = run_levels(client, config) if args.mode == "levels" else run_pii(client, config, args.n)
    if args.output is None:
        args.output = EVAL_DIR / f"eval_report_{args.mode}.csv"

    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mode", "file", "expected", "predicted", "error"])
        writer.writeheader()
        writer.writerows(rows)

    print(report_levels(rows) if args.mode == "levels" else report_pii(rows))
    errors = sum(1 for r in rows if r["error"])
    print(f"\n{len(rows)} samples, {errors} errors. Detail: {args.output}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
