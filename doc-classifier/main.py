"""基于 Meta ClassifyIt 方法论的本地 markdown 敏感度分级工具。"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import yaml
from openai import OpenAI

from logic import DIMENSIONS, resolve

logger = logging.getLogger("doc_classifier")

CSV_FIELDS = [
    "file_name",
    "category_matched",
    "security_category",
    "needs_review",
    "review_reasons",
    "brief_explanation",
    "error",
]


def load_dotenv(path: Path) -> dict:
    """解析 KEY=VALUE 格式的 .env 文件（支持 # 注释与引号值）。"""
    if not path.exists():
        return {}
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def apply_env_overrides(config: dict, env_path: Path | None = None) -> None:
    """LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 覆盖 config.yaml。

    优先级：系统环境变量 > .env 文件 > config.yaml。用于接入任何 OpenAI 兼容 API。
    """
    env = load_dotenv(env_path or Path(__file__).parent / ".env")
    env.update({k: os.environ[k] for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if k in os.environ})
    if env.get("LLM_BASE_URL"):
        config["llm_server"]["base_url"] = env["LLM_BASE_URL"]
    if env.get("LLM_API_KEY"):
        config["llm_server"]["api_key"] = env["LLM_API_KEY"]
    if env.get("LLM_MODEL"):
        config["llm_server"]["model"] = env["LLM_MODEL"]


def extract_json(text: str) -> dict:
    """从模型回复中提取 ```json 代码块，回退到首个 {...}。"""
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    raw = match.group(1) if match else text[text.index("{") : text.rindex("}") + 1]
    return json.loads(raw)


def classify_content(client: OpenAI, config: dict, content: str) -> dict:
    """调用 LLM 分析文档，经分类逻辑层裁决后返回结果（保留 category_matched 键）。"""
    agent = config["agent_settings"]
    categories = json.dumps(agent["response_categories"], ensure_ascii=False)
    catalog = json.dumps(config.get("logic", {}).get("information_types", {}), ensure_ascii=False)
    response = client.chat.completions.create(
        model=config["llm_server"]["model"],
        messages=[
            {"role": "system", "content": f"{agent['agent_instructions']}\n\nValid categories: {categories}"},
            {
                "role": "user",
                "content": (
                    f"{agent['prompt']}\n\n"
                    f"Information type catalog (baseline ratings, rate higher only with evidence):\n{catalog}\n\n"
                    f"<document>\n{content[:5000]}\n</document>"
                ),
            },
        ],
        temperature=0.1,
    )
    analysis = extract_json(response.choices[0].message.content)
    logic = config.get("logic", {})
    result = resolve(analysis, logic.get("information_types", {}), logic)
    return {
        "category_matched": result["category_matched"],
        "brief_explanation": str(analysis.get("brief_explanation", "")),
        **result,
    }


def classify_file(client: OpenAI, config: dict, path: Path, max_retries: int = 3) -> dict:
    """对单个文件分级，带指数退避重试。"""
    content = path.read_text(encoding="utf-8")
    delay = 1
    for attempt in range(max_retries):
        try:
            result = classify_content(client, config, content)
            return {
                "file_name": path.name,
                "category_matched": result["category_matched"],
                "security_category": "/".join(result["security_category"][d] for d in DIMENSIONS),
                "needs_review": result["needs_review"],
                "review_reasons": "; ".join(result["review_reasons"]),
                "brief_explanation": result["brief_explanation"],
                "error": "",
            }
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("Failed to classify %s: %s", path.name, e)
                return {
                    "file_name": path.name,
                    "category_matched": "",
                    "security_category": "",
                    "needs_review": "",
                    "review_reasons": "",
                    "brief_explanation": "",
                    "error": str(e),
                }
            logger.warning("Attempt %d failed for %s: %s, retrying in %ds", attempt + 1, path.name, e, delay)
            time.sleep(delay)
            delay *= 2
            return {f: "" for f in CSV_FIELDS}  # unreachable, keeps type checkers happy


def run(directory: Path, config_path: Path, output_csv: Path) -> list[dict]:
    """扫描目录下所有 .md 文件并分级，写出 CSV。"""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    apply_env_overrides(config)
    client = OpenAI(base_url=config["llm_server"]["base_url"], api_key=config["llm_server"].get("api_key", "ollama"))
    md_files = sorted(directory.rglob("*.md"))
    logger.info("Found %d markdown files in %s", len(md_files), directory)
    results = [classify_file(client, config, f) for f in md_files]

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results)
    logger.info("Results written to %s", output_csv)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify markdown files' sensitivity level using a local LLM")
    parser.add_argument("--dir", type=Path, required=True, help="Directory containing .md files to scan")
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "config.yaml")
    parser.add_argument("--output", type=Path, default=Path("classification_result.csv"))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    results = run(args.dir, args.config, args.output)
    failed = sum(1 for r in results if r["error"])
    print(f"Done: {len(results)} files, {failed} errors. See {args.output}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
