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

from main import classify_content

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
    """从 OpenPII 验证集抽中英各半样本（含 PII/脱敏各 n_per_class 条）。

    只保留 zh/en 两种语言。结果缓存到本地 JSON，固定随机种子，保证多次运行样本一致。
    """
    cache = EVAL_DIR / "pii_cache" / "sample.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    from datasets import load_dataset

    ds = load_dataset("ai4privacy/pii-masking-openpii-1.5m", split="validation")
    zh = [r for r in ds if r["language"] == "zh"]
    en = [r for r in ds if r["language"] == "en"]
    zh_pos = [r["source_text"] for r in zh if r["privacy_mask"]]
    zh_neg = [r["masked_text"] for r in zh if not r["privacy_mask"]]
    en_pos = [r["source_text"] for r in en if r["privacy_mask"]]
    en_neg = [r["masked_text"] for r in en if not r["privacy_mask"]]
    for name, pool in (("zh-pos", zh_pos), ("zh-neg", zh_neg), ("en-pos", en_pos), ("en-neg", en_neg)):
        if len(pool) < n_per_class / 2:
            raise ValueError(f"OpenPII validation split has too few {name} samples: {len(pool)}")
    rng = random.Random(42)
    half = n_per_class // 2
    sample = {
        "positive": rng.sample(zh_pos, half) + rng.sample(en_pos, n_per_class - half),
        "negative": rng.sample(zh_neg, half) + rng.sample(en_neg, n_per_class - half),
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
    parser.add_argument("--output", type=Path, default=EVAL_DIR / "eval_report.csv")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    client = OpenAI(base_url=config["llm_server"]["base_url"], api_key="ollama")
    rows = run_levels(client, config) if args.mode == "levels" else run_pii(client, config, args.n)

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
