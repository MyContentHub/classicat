# doc-classifier

本地 markdown 文件敏感度分级工具，方法论借鉴 [Meta ClassifyIt](https://github.com/meta-llama/PurpleLlama/tree/main/SensitiveDocClassification)（PurpleLlama/SensitiveDocClassification）。

与原版的差异：去掉了 Google Workspace 依赖（文件来源改为本地目录、文档解析直接读纯文本、结果输出为 CSV 而非写回 Drive 标签），LLM 通过 Ollama 的 OpenAI 兼容接口直连，跳过 Llama Stack 中间层。

## 使用

```bash
uv sync
# 先启动 ollama 并拉模型
ollama pull llama3.2:3b
# 运行分级
uv run main.py --dir <markdown 目录> --output result.csv
# 运行测试
uv run pytest
```

分类类别、prompt、模型在 `config.yaml` 中配置。默认四级：public / internal / restricted / confidential。
