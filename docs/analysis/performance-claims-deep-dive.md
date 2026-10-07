# 小众项目性能宣称深度核验：TorchSight 95% 与 eai-distill 70 req/s

> 日期：2026-10-07
> 任务来源：上一轮调研修订结论中"小众项目的性能宣称（TorchSight 95%、eai-distill 70 req/s）仍不可直接采信"待深入验证

## 一、总结论

**两个数字都查到了确切出处，均非幻觉；但都不能作为选型依据直接采信——且原因不同。**

| 宣称 | 核验结果 | 修正后的可用表述 |
|---|---|---|
| TorchSight "95% 准确率" | 真实评测结果，但测在**自家合成模板基准**上；论文盲标复验拉低到 90.8%，作者 ROADMAP 自评真实场景 ~85–92% | "英文合成基准 95.0%；人工盲标 90.8%；真实文档作者自评 ~85–92%；中文完全未验证" |
| eai-distill "70 req/s" | 出自有论文背书的 Table 12，条件完整且**数字内部自洽**；但它是每 GPU 批量标注吞吐，质量指标是 κ 一致率而非准确率，领域是英文网页分类 | "70.28 req/s/GPU（MI300x、批量、prefix caching、压缩输出、英文网页）；κ 0.72；与中文文件分级无关，仅蒸馏方法可借鉴" |

一个重要的元发现：**DeepSeek 这次没有编造这两个数字**——它准确转述了结果，但剥离了全部测量条件。这印证了"LLM 调研的可靠性分层"：具体数字往往有出处，上下文条件才是最先丢失的部分。

## 二、TorchSight 95% 核验

### 2.1 存在性与出处（全部确认）

| 资源 | 状态 |
|---|---|
| GitHub `IvanDobrovolsky/torchsight` | 存在，168 commits，Apache 2.0，1 star / 0 fork |
| HuggingFace `torchsight/beam-q4_K_M`、`beam-q8_0`、`beam-f16` | 公开可下载（HTTP 200，q4_K_M 约 17GB GGUF） |
| arXiv 2605.20368（2026-05-19，单作者，CC-BY） | 存在，题为《Security Document Classification with a Fine-Tuned Local Large Language Model》 |
| 训练配置 | Qwen 3.5 27B + LoRA（r=128, alpha=256, 5 epochs），78,358 样本，8×A100 10.5 小时，公开可复现 |
| 训练数据集 `torchsight/security-dataset` | 存在但 **HTTP 401（gated，需申请）**，盲标复验材料"随数据集发布"的说法暂无法公开核验 |

### 2.2 评测方法（认真程度超出 1-star 项目的预期）

双基准设计，全部脚本公开：

- **Eval-1000（合成）**：Faker + 模板程序化生成，7 类 × 51 子类分层，含 100 张图片样本；结果 95.0% [93.5, 96.2]（Wilson CI）
- **Eval-500（外部 held-out）**：来自 NVD/NIST/AI4Privacy/Enron/phishing 的**同源未见过样本** + MTSamples（明确不参与训练）；SHA-256 前 500 字符去重；320/500 允许双标签；结果 93.8% [91.3, 95.6]
- 有 McNemar 检验脚本、商用模型对比（Claude 4 / GPT-5 / Gemini 2.5）、48 条正则基线、未微调 Qwen base 消融
- 论文 §7.6 有**盲标复验**：两名独立评审盲标 200 样本，κ = 0.984（标注质量高），裁决后 Beam q4_K_M 为 **90.8% / macro-F1 89.8%**（n=195）

### 2.3 六个打折理由（按严重程度排序）

1. **合成基准与训练数据同生成器家族（结构性证实）**。训练生成器 `beam/scripts/processors/synth_generator.py` 与评测生成器 `beam/evaluation/scripts/generate_eval_1000.py` 使用相同的 helper 函数（`rand_hex`/`rand_b64`）、相同的密钥格式族（AKIA…/sk_live_…/ghp_…/xoxb-…/sk-…）、相同的模板+Faker 方法。95.0% 本质是**同分布模板识别成绩**。论文自认："这种分离不能消除所有分布重叠，尤其是合成数据"。
2. **论文自己的盲标复验把数字拉到 90.8%**。人工裁决标签后（而非模板构造标签），准确率下降 4.2pp——这是最可信的单一数字。
3. **作者 ROADMAP 自评真实场景更差**：真实财务文档 ~85%，全管线（Beam+正则+OCR）真实场景 ~92%（对比评测集 97.6%）。作者诚实，但这正是"95% 不可直接采信"的权威来源。
4. **商用基线对比不公平，论文自认**。§8.3："Beam 用训练时的同一 system prompt 评测，商用模型只在测试时拿到该 prompt——这可能使基线处于劣势"。GPT-5 还被迫 temp=1（仅它不支持 0）。"本地微调打赢 GPT-5"的说法要打折扣。
5. **论文与仓库自相矛盾**：论文称所有模型 temperature=0 一视同仁；仓库评测 README 却写明"Beam 跑训练默认 0.1，商用模型跑 0"的已知不对称。两处必有一处过时，复现时需以仓库为准并自行确认。
6. **场景不匹配**：论文 §8.3 第五条明确"仅英文、单标签，多语言留作未来工作"；51 子类细粒度只有 48.2%；医疗类召回仅 68%（外部 MTSamples 上 82%，被商用模型反超）。中文企业文档四级分级 = 完全外推。

### 2.4 对本项目的可用判断

- **架构参考价值依然成立**（双基准设计、hard negatives、盲标复验、正则兜底都是可抄的作业）
- 预期应设为：英文真实文档 ~90%、边界类别更差、中文未知；相对增益真实（vs 未微调 base +7~9pp）
- 单作者、零独立复现（0 fork、数据集 gated）意味着任何数字都只能当作"作者自测"而非"社区验证"

## 三、eai-distill-0.5b 70 req/s 核验

### 3.1 出处（比预期硬：有同行可查论文）

arXiv 2506.14111v2《Essential-Web v1.0: 24T tokens of organized web data》（Essential AI 团队，含 Ashish Vaswani）Table 12：

| 配置 | RPS/GPU | 相对加速 |
|---|---:|---:|
| Qwen2.5-32B + 原始 prompt + 原始输出（基线） | 1.40 | 1.0× |
| Qwen2.5-0.5B + 无 prompt + 压缩输出（**EAI-Distill 配置**） | **70.28** | **50.20×** |
| 同模型 + 分类头（对照） | 189.23 | 135.16× |

测量条件（论文明示）：**requests per second per GPU**（每 GPU）、prefix caching 开启、vLLM、大批量吞吐优先、生成走压缩格式、prompt 经上下文蒸馏完全移除。推理硬件：**512× AMD MI300x 跑约 1 周（≈90k GPU-hours）标注 23.6B 文档**。

### 3.2 内部一致性检验（通过，这是可信度的关键加分项）

- 23.6B docs ÷ (90,000 GPU-h × 3600s) ≈ **72.7 docs/s/GPU ≈ 70.28** ✓
- 90k GPU-h ÷ 512 GPU ≈ 175.8h ≈ **7.3 天** ✓

吞吐数字与总标注预算互相印证，不是孤立宣称。

### 3.3 四个不可迁移到本项目的理由

1. **per-GPU 批量吞吐 ≠ 你能买到的服务能力**。它假设工业级批量、prefix caching、MI300x；单流或小批量推理（消费者 GPU、transformers 单请求）会低一个数量级以上。
2. **管线特化**。"无 prompt + 压缩输出"是为 24T token 标注定制的上下文蒸馏方案，换任务（如机密分级的长 prompt + JSON 论证输出）即失效。
3. **质量指标是一致率不是准确率**。κ 0.71–0.74 是对"金标标注者"（GPT-4o 和 Claude 3.5 Sonnet——本身是 LLM）的一致性；对教师 Qwen2.5-32B 是 0.74→0.72（相对差 3%）。κ≈0.72 属"substantial"，距离"可独立信任"有距离，且没有任何人工专家金标。
4. **领域完全错位**。模型卡明示："Optimized for English web documents extracted using resiliparse"、"categories based on web content patterns and may not generalize to other document types"。12 类网页分类学（FDC/Bloom/文档类型/教育元数据）与中文企业文件机密四级分级零重叠。

### 3.4 对本项目的可用判断

- **可借鉴的是方法论**：教师大模型标注 → 0.5B 学生蒸馏 + 压缩输出 + prefix caching，适合未来做"海量存量文件初筛"（若真有亿级文件需求再启用）
- **不可引用为**："本地 0.5B 模型能以 70 req/s 给我们的文件分级"

## 四、方法论沉淀：小众项目性能宣称五步核验清单

本轮验证过程抽象为可复用流程，供后续任何"看起来太好的数字"使用：

1. **出处定位**：数字来自论文表格、README 还是二手转述？有无比宣传页更硬的出处（本轮：两者都有论文级出处，超预期）
2. **测量条件还原**：硬件型号、per-GPU 还是 per-system、批量还是单流、输出长度、prompt/温度——缺失条件的数字等于没有数字
3. **基准独立性判定**：合成还是真实？"held-out"是同源未见过还是异源？标签来自人工、构造还是推导？（TorchSight 的"external"实为同源 held-out + 源推导标签）
4. **内部一致性算术**：吞吐 × 时长 × 硬件数 ≈ 总量？（eai 通过；TorchSight 无此检验点）
5. **自我矛盾扫描**：论文 vs 仓库 README vs ROADMAP 自评；宣传数字 vs 作者自己的限制声明（TorchSight 论文/README 温度矛盾、ROADMAP ~85% vs 摘要 95%）

## 五、对既有文档的修正说明

- `docs/deepseek-analysis-report.md` 第三节旧判定（TorchSight/eai-distill 标为幻觉）**已过时**，以 handoff 第三节三档名单 + 本文档核验结果为准；该报告的更新仍待执行
- handoff "其他数据点"中"eai-distill 70 req/s 未经独立复核"现在可以升级为：**已复核至论文级出处、内部自洽，但条件不可迁移**；TorchSight 95% 升级为：**出处确认，论文自带盲标与 ROADMAP 自评数据，操作数字应按 90.8%（盲标）/ ~85–92%（真实场景）折算，中文未验证**
