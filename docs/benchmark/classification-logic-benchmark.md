# doc-classifier Benchmark 报告

> 日期：2026-10-08 · 关联文档：[分类逻辑层设计方案](../plans/classification-logic-design.md)
> levels 分级结果全部来自 2026-10-08 样本去污染后的干净基准
>（早期样本正文首行带密级贴纸，属答案泄漏，相关数据已移除，不复现）；
> pii 结果为 2026-10-07/08 轮，数据集未随去污染重跑，阴性池缓存已失效删除。

## 一、测试环境与方法

- 模型：本地 Ollama `qwen2.5:latest`（Qwen2.5-7B，Q4_K_M）、云端 `deepseek-flash`、
  云端 `deepseek-v4-pro`（均走 `api.deepseek.com`，temperature 0.1）
- 每轮开始前用预检请求确认 API 实际返回的 `response.model`，
  防止配置错写时静默回落到错误模型（首轮曾因此作废过数据）
- levels 样本：自建 80 个（四级各 20，中英双语，含 boundary 边界样本），
  文件名前缀即标准答案，2026-10-08 已清理 34 个文件 45 处正文密级贴纸
  （保留"已授权公开引用"等业务性用法——它们是 boundary 样本的推理依据）
- pii 样本：ai4privacy/pii-masking-openpii-1.5m 验证集 200 条阳性（中英各半）
  + 自建真干净文本 42 条阴性，固定随机种子

两个评测模式（[run_eval.py](../../doc-classifier/eval/run_eval.py)）：
levels 测混淆矩阵 / accuracy / 不足分类率（安全红线）/ 过度分类率；
pii 测 PII 召回率（被判 confidential）与误报率。

## 二、分模型结果

| 模型 | levels 准确率 | 不足分类率 | 过度分类率 | PII 召回率 | PII 误报率 |
|---|---|---|---|---|---|
| qwen2.5:7b（本地） | 82.5%（66/80） | **16.2% ⚠️** | 1.2% | 79.0%（158/200） | 0%（0/42） |
| deepseek-flash | **83.8%（67/80）** | **0%** | 16.2% | **91.0%（182/200）** | 4.8%（2/42） |
| deepseek-v4-pro | 81.2%（65/80） | **0%** | 18.8% | 未测 | — |

### qwen2.5:7b（本地 Ollama）

levels 混淆矩阵（expected \ pred）：

|  | public | internal | restricted | confidential |
|---|---|---|---|---|
| public | 21 | 0 | 0 | 0 |
| internal | 4 | 21 | 0 | 0 |
| restricted | 5 | 3 | 8 | 1 |
| confidential | 0 | 1 | 0 | 16 |

准确率与云端接近，但错误方向危险：13 篇错误里 12 篇是低判，含 5 篇
restricted → public（竞品分析、定价策略、核心架构、重组预案等全部漏到
公开档）。本地 7B 未建立"宁高勿低"偏置，隐私敏感场景不可直接落地；
下一步在 `agent_instructions` 追加一行保守倾向指令（"When uncertain
between two levels, choose the higher one"）即可复测，无需改代码。

### deepseek-flash

levels 混淆矩阵（expected \ pred）：

|  | public | internal | restricted | confidential |
|---|---|---|---|---|
| public | 18 | 2 | 0 | 1 |
| internal | 0 | 21 | 3 | 1 |
| restricted | 0 | 0 | 11 | 6 |
| confidential | 0 | 0 | 0 | 17 |

唯一低判为 0 的模型之一，安全底线最稳。13 篇高判中 6 篇为
restricted → confidential（M&A 草稿、定价策略等"商业敏感"文本），
均被 `needs_review` 方向化标记（over），可作为目录基线调优信号。
PII 召回 91% 显著领先，误报 2 篇被复核标记兜住。

### deepseek-v4-pro

levels 混淆矩阵（expected \ pred）：

|  | public | internal | restricted | confidential |
|---|---|---|---|---|
| public | 20 | 0 | 0 | 1 |
| internal | 0 | 20 | 4 | 1 |
| restricted | 0 | 0 | 8 | 9 |
| confidential | 0 | 0 | 0 | 17 |

准确率低于 flash（81.2% vs 83.8%），且明显更保守：15 篇高判里
9 篇是 restricted → confidential，几乎所有商业敏感文本都被推到最高档。
低判守住 0，但对 levels 任务而言，"高水位线 + 目录基线"已硬编码保守
偏置，模型自身的保守倾向只是冗余放大；单轮耗时约为 flash 的 3 倍
（~25 分钟 vs ~8 分钟），性价比完败。

## 三、结论

- **落地策略**：分级场景首选 deepseek-flash（最准、最快、低判 0）；
  本地 7B 须先修保守偏置再用于隐私敏感场景；v4-pro 对本任务无增益。
- **pii 防护不依赖模型稳定性**：qwen 召回 79% vs flash 91%，漏报均发生
  在语义层（LLM 未上报 PII 信息类型）；一旦上报，目录基线
  `员工客户PII: c: high` 的硬兜底保证最终标签为 confidential，逻辑层
  不引入漏报。flash 的 2 篇误报被复核标记兜住。
- 逻辑层架构此前已在早期样本集通过对旧管线的红线验收（不足分类近半
  下降、PII 无显著回退），本报告聚焦去污染后的模型横向对比。

## 四、产物与复现

明细 CSV（gitignore，本地保留于 `doc-classifier/eval/`）：

- `eval_report_levels_deepseek_clean.csv`（干净样本云端 flash 轮）
- `eval_report_levels_qwen25_7b_clean.csv`（干净样本本地 7B 轮）
- `eval_report_levels_deepseek_v4pro_clean.csv`（干净样本云端 v4-pro 轮）
- `eval_report_pii_baseline.csv` / `eval_report_pii_logic.csv`（7B pii 轮）
- `eval_report_pii_deepseek.csv`（flash pii 轮）

复现（levels，切模型只需改 `LLM_MODEL`）：

```bash
cd doc-classifier
# 本地 7B
export LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama LLM_MODEL=qwen2.5:latest
# 云端则不设覆盖，走 doc-classifier/.env 的 DeepSeek 配置
uv run eval/run_eval.py --mode levels --output eval/eval_report_levels_<model>_clean.csv
```

pii（阴性池缓存已删除，自动用去污染样本重建）：

```bash
cd doc-classifier
uv run eval/run_eval.py --mode pii --output eval/eval_report_pii_<model>.csv
```
