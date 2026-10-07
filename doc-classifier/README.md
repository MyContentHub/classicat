# doc-classifier

本地 markdown 文件敏感度分级工具，方法论借鉴 [Meta ClassifyIt](https://github.com/meta-llama/PurpleLlama/tree/main/SensitiveDocClassification)（PurpleLlama/SensitiveDocClassification）。

与原版的差异：去掉了 Google Workspace 依赖（文件来源改为本地目录、文档解析直接读纯文本、结果输出为 CSV 而非写回 Drive 标签），LLM 通过 Ollama 的 OpenAI 兼容接口直连，跳过 Llama Stack 中间层；并新增自研分类逻辑层——LLM 只做语义分析（信息类型识别 + C/I/A 评级），评级校验、FIPS 199 高水位线聚合与四级映射由纯代码完成，可审计、可单测、不随模型波动。

## 前置条件

- Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)
- 本地 [Ollama](https://ollama.com) 服务在跑（Windows 默认开机自启），模型自动按需加载进显存
- 显存 ≥ 6GB 即可跑 qwen2.5:7b（Q4 量化约 4.4GB，32K 上下文）

## 使用

```bash
uv sync
# 拉取模型（首次）
ollama pull qwen2.5:7b
# 运行分级
uv run main.py --dir <markdown 目录> --output result.csv
# 运行测试
uv run pytest
```

分类类别、prompt、模型、种子信息类型目录在 `config.yaml` 中配置。默认四级：public / internal / restricted / confidential。
LLM 只做语义分析（识别信息类型并逐类型给 C/I/A 评级 + 证据），
`logic.py` 按目录基线兜底与 FIPS 199 高水位线裁决出最终 `category_matched`；
裁决结果含 `security_category`、`needs_review`（低置信度 / 待归类类型 / 与 LLM 建议不符时标记复核）。
带指数退避重试（3 次），失败文件在 CSV 的 `error` 列标注。

### 接入云端 API

复制 `.env.example` 为 `.env`，填入 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 即可接入任何
OpenAI 兼容 API（如 DeepSeek），覆盖 `config.yaml` 的本地 Ollama 配置。`.env` 已被 gitignore，密钥不入库。

## 基准测试

社区集测 PII 召回，自建集测分级边界：

| 模式 | 数据 | 指标 |
|---|---|---|
| `--mode levels` | 自建 80 个中英双语样本（4 级各 20），文件名前缀即标准答案 | 混淆矩阵、每级准确率、不足分类率（安全关键）、过度分类率 |
| `--mode pii` | [ai4privacy/pii-masking-openpii-1.5m](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1.5m) 验证集抽样 200 条阳性（中英各半）+ 自建 public/internal 样本全量作阴性 | PII 召回率（含 PII 被判机密）、误报率（干净文本被判机密） |

```bash
# 单独拉取 PII 样本并预览（不调 LLM），供人工检查后供 pii 模式复用
uv run eval/fetch_pii.py --n 20

# 跑基准
uv run eval/run_eval.py --mode levels
uv run eval/run_eval.py --mode pii --n 100   # --n 可调小快速冒烟
```

PII 样本缓存于 `eval/pii_cache/sample.json`（固定随机种子，多次运行一致；删除后重跑可重新抽样）。
首次运行 `--mode pii` 会从 HuggingFace 下载数据集（几百 MB）。结果明细按模式写入 `eval/eval_report_<mode>.csv`。

最新一轮结果（分类逻辑层落地后）：levels accuracy 87.5%、不足分类率 8.8%、过度分类率 3.8%，
PII 误报率 0.0%，双向防护红线全部达标，详见
[benchmark 报告](../docs/benchmark/classification-logic-benchmark.md)。

## 项目结构

```
doc-classifier/
├── config.yaml          # 分级配置（instructions / prompt / 四级定义 / 模型）
├── logic.py             # 分类逻辑层：基线兜底 → 高水位线 → 标签映射 → 复核标记（纯函数）
├── main.py              # CLI：读 md → LLM 分级 → CSV
├── test_logic.py        # 逻辑层裁决规则自检（不调 LLM）
├── test_main.py         # JSON 提取与 CSV 输出自检
└── eval/
    ├── run_eval.py      # 基准测试入口（levels / pii 两种模式）
    ├── fetch_pii.py     # PII 样本拉取与预览
    ├── eval_samples/    # 自建样本集（文件名前缀 = 标准答案）
    └── pii_cache/       # OpenPII 抽样缓存（gitignore）
```
