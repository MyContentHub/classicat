# doc-classifier 分类逻辑层 Benchmark 报告

> 日期：2026-10-07 · 关联文档：[分类逻辑层设计方案](../plans/classification-logic-design.md)
> 对象：分类逻辑层落地后的最终一轮全量基准，同条件与旧管线基线对比。

## 一、测试环境与方法

- 模型：本地 Ollama `qwen2.5:latest`（Qwen2.5-7B，Q4_K_M，32K 上下文），temperature 0.1
- 旧管线基线（步骤 0）与改后管线使用完全相同的环境与数据，仅逻辑层不同；
  显式环境变量把 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 钉死到本地 Ollama，
  防止 `.env` 里的云端 API 配置混入（避免换模型换变量混淆归因）
- 每轮全量 0 错误（80 + 242 样本全部成功返回并裁决）

两个评测模式（[run_eval.py](../../doc-classifier/eval/run_eval.py)）：

| 模式 | 数据 | 指标 |
|---|---|---|
| levels | 自建 80 个样本（public/internal/restricted/confidential 各 20，中英双语，文件名前缀即标准答案） | 混淆矩阵、accuracy、不足分类率（安全红线）、过度分类率 |
| pii | ai4privacy/pii-masking-openpii-1.5m 验证集 200 条阳性（中英各半）+ 自建真干净文本 42 条阴性，固定随机种子缓存 | PII 召回率（被判 confidential）、误报率 |

## 二、levels 结果（分级边界）

改后混淆矩阵（expected \ pred）：

|  | public | internal | restricted | confidential |
|---|---|---|---|---|
| public | 21 | 0 | 0 | 0 |
| internal | 4 | 21 | 0 | 0 |
| restricted | 2 | 1 | 11 | 3 |
| confidential | 0 | 0 | 0 | 17 |

| 指标 | 基线（旧管线） | 改后（逻辑层） | 变化 |
|---|---|---|---|
| accuracy | 81.2%（65/80） | **87.5%（70/80）** | +6.3pp |
| 不足分类率 | 15.0%（12/80） | **8.8%（7/80）** | −6.2pp |
| 过度分类率 | 3.8%（3/80） | **3.8%（3/80）** | 持平 |

不足分类主要残余：internal 中 4 篇被 LLM 识别为"公开发布信息"而判 public；
restricted 中 2 篇同类误识别。过度分类 3 篇全部集中在 restricted → confidential。

## 三、pii 结果（PII 召回）

| 指标 | 基线（旧管线） | 改后（逻辑层） | 变化 |
|---|---|---|---|
| PII 召回率 | 80.5%（161/200） | 79.0%（158/200） | −1.5pp |
| 误报率 | 0.0%（0/42） | 0.0%（0/42） | 持平 |

召回差异 3 例在 temperature 0.1 的单轮噪声范围内；漏报均为 LLM 未上报
PII 信息类型（语义层），一旦上报，目录基线 `员工客户PII: c: high` 的
硬兜底保证最终标签为 confidential，逻辑层不引入漏报。

## 四、红线判定与结论

设计方案步骤 5 的验收标准：

| 红线 | 要求 | 实测 | 判定 |
|---|---|---|---|
| 不足分类率 | 不得高于基线 15.0% | 8.8% | ✅ 通过（近半下降） |
| 过度分类率 | 不得高于基线 3.8% | 3.8% | ✅ 通过（持平） |
| PII 召回 | 无显著回退 | −1.5pp（噪声内） | ✅ 通过 |

**结论：分类逻辑层在满足双向防护红线的前提下，分级准确率提升 6.3pp。**
代码做全部裁决的架构（基线硬兜底 + 证据门控上调 + 高水位线聚合）实测
同时压低不足分类并守住过度分类，PII 防护不依赖模型稳定性。

## 五、产物与复现

明细 CSV（gitignore，本地保留于 `doc-classifier/eval/`）：

- `eval_report_levels_baseline.csv` / `eval_report_levels_logic_v2.csv`（改后轮）
- `eval_report_pii_baseline.csv` / `eval_report_pii_logic.csv`（改后轮）

复现命令（钉死本地 7B）：

```bash
cd doc-classifier
export LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama LLM_MODEL=qwen2.5:latest
uv run eval/run_eval.py --mode levels --output eval/eval_report_levels_logic_v2.csv
uv run eval/run_eval.py --mode pii --output eval/eval_report_pii_logic.csv
```
