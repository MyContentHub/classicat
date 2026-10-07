"""单独拉取 OpenPII 样本（仅中英文，中英各半）并打印预览，供人工检查。

用法：
    uv run eval/fetch_pii.py            # 抽 100 条/类（与 pii 模式默认一致）
    uv run eval/fetch_pii.py --n 20     # 小规模快速检查
"""

import argparse
from pathlib import Path

from run_eval import EVAL_DIR, build_sample


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and preview OpenPII samples (zh/en only)")
    parser.add_argument("--n", type=int, default=100, help="每类抽样条数（与 run_eval --mode pii --n 一致）")
    parser.add_argument("--show", type=int, default=3, help="每类预览条数")
    args = parser.parse_args()

    sample = build_sample(args.n)
    cache = EVAL_DIR / "pii_cache" / "sample.json"
    print(f"cached: {cache}")
    for label, texts in sample.items():
        zh_count = sum(1 for t in texts if any("\u4e00" <= c <= "\u9fff" for c in t[:50]))
        print(f"\n== {label}: {len(texts)} samples (approx zh/en: {zh_count}/{len(texts) - zh_count}) ==")
        for i, text in enumerate(texts[: args.show]):
            preview = text[:150].replace("\n", " ")
            print(f"[{i}] {preview}{'...' if len(text) > 150 else ''}")


if __name__ == "__main__":
    main()
