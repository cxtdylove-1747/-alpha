# scripts/legacy/build_high_quality.py

从零构建高质量创新创业知识图谱（KG）与超图（Hypergraph）。

## 特性

- 质量优先：每个节点/关系/超边都要求有证据来源
- 支持 `pdf/doc/docx/pptx/txt/md` 多类型案例解析
- DeepSeek 优先抽取（失败重试），失败后可降级 OpenAI，再降级规则 fallback
- 无 API Key 时可直接运行：启用整文高质量规则抽取（`fallback_doc`）
- 自动识别赛事（创新创业赛 / 挑战杯）与奖项（默认一等奖）
- 显式创建竞赛资源节点并建立 `REQUIRES_RESOURCE` 关联
- 生成审计日志 `extraction_log.json` 与质量报告 `quality_report.txt`

## 依赖

- Python 3.8+
- `requests`
- 可选：`pdfplumber`（解析 PDF）

## 运行

```bash
python scripts/legacy/build_high_quality.py --data-dir ./data --deepseek-key sk-xxxxx
```

可选 OpenAI 备用：

```bash
python scripts/legacy/build_high_quality.py --data-dir ./data --deepseek-key sk-xxxxx --openai-key sk-xxxxx
```

无 key 本地高质量规则模式：

```bash
python scripts/legacy/build_high_quality.py --data-dir ./data --output-dir ./output_v2/hq_rebuild
```

## 输出

默认输出到当前目录（可用 `--output-dir` 指定）：

- `kg_nodes.json`
- `kg_relations.json`
- `hypergraph_edges.json`
- `quality_report.txt`
- `extraction_log.json`

