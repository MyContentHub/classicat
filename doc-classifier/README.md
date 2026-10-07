# doc-classifier

本地 markdown 文件敏感度分级工具，方法论借鉴 [Meta ClassifyIt](https://github.com/meta-llama/PurpleLlama/tree/main/SensitiveDocClassification)（PurpleLlama/SensitiveDocClassification）。

与原版的差异：去掉了 Google Workspace 依赖（文件来源改为本地目录、文档解析直接读纯文本、结果输出为 CSV 而非写回 Drive 标签），LLM 通过 Ollama 的 OpenAI 兼容接口直连，跳过 Llama Stack 中间层。

## 前置条件

- Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)
- 本地 [Ollama](https://ollama.com) 服务在跑（Windows 默认开机自启），模型自动按需加载进显存
- 显存 ≥ 4GB 即可跑 llama3.2:3b（Q4 量化约 2GB）；实测 RTX 3060 12GB 上模型热后单次请求约 1s

## 使用

```bash
uv sync
# 拉取模型（首次）
ollama pull llama3.2:3b
# 运行分级
uv run main.py --dir <markdown 目录> --output result.csv
# 运行测试
uv run pytest
```

分类类别、prompt、模型在 `config.yaml` 中配置。默认四级：public / internal / restricted / confidential。
模型返回 JSON（`category_matched` + `brief_explanation`），带指数退避重试（3 次），失败文件在 CSV 的 `error` 列标注。

### 接入云端 API

复制 `.env.example` 为 `.env`，填入 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 即可接入任何
OpenAI 兼容 API（如 DeepSeek），覆盖 `config.yaml` 的本地 Ollama 配置。`.env` 已被 gitignore，密钥不入库。

## 基准测试

社区集测 PII 召回，自建集测分级边界：

| 模式 | 数据 | 指标 |
|---|---|---|
| `--mode levels` | 自建 20 个中文样本（4 级 × [3 典型 + 2 边界]），文件名前缀即标准答案 | 混淆矩阵、每级准确率、不足分类率（安全关键）、过度分类率 |
| `--mode pii` | [ai4privacy/pii-masking-openpii-1.5m](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1.5m) 验证集抽样，仅中英文、中英各半，默认 100 条/类 | PII 召回率（含 PII 被判机密）、误报率（干净文本被判机密） |

```bash
# 单独拉取 PII 样本并预览（不调 LLM），供人工检查后供 pii 模式复用
uv run eval/fetch_pii.py --n 20

# 跑基准
uv run eval/run_eval.py --mode levels
uv run eval/run_eval.py --mode pii --n 100   # --n 可调小快速冒烟
```

PII 样本缓存于 `eval/pii_cache/sample.json`（固定随机种子，多次运行一致；删除后重跑可重新抽样）。
首次运行 `--mode pii` 会从 HuggingFace 下载数据集（几百 MB）。结果明细按模式写入 `eval/eval_report_<mode>.csv`。

## 项目结构

```
doc-classifier/
├── config.yaml          # 分级配置（instructions / prompt / 四级定义 / 模型）
├── main.py              # CLI：读 md → LLM 分级 → CSV
├── test_main.py         # JSON 提取与 CSV 输出自检
└── eval/
    ├── run_eval.py      # 基准测试入口（levels / pii 两种模式）
    ├── fetch_pii.py     # PII 样本拉取与预览
    ├── eval_samples/    # 自建样本集（文件名前缀 = 标准答案）
    └── pii_cache/       # OpenPII 抽样缓存（gitignore）
```
