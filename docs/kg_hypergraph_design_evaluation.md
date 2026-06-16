# 本项目知识图谱与超图设计及评估文档（KG/HG）

## 1. 文档目的与范围

本文档用于说明本项目知识图谱（Knowledge Graph, KG）与超图（Hypergraph, HG）的：

- 设计目标与核心原则
- 数据模型与构建流程
- 运行时消费方式（诊断/评分）
- 评估方法与当前基线结果（截至 2026-04-24）

本文档以当前主流程 `scripts/rebuild_kg_hypergraph_v3.py` 及根目录产物 `kg_nodes.json / kg_relations.json / hypergraph_edges.json` 为主口径。

---

## 2. 版本与产物口径

### 2.1 当前主版本

- Schema 版本：`kg_hg_v3`
- 主要构建脚本：`scripts/rebuild_kg_hypergraph_v3.py`
- 当前根目录数据规模（2026-04-24）：
  - 节点：2745
  - 关系：2790
  - 超边：777

### 2.2 历史/兼容链路

- 历史构建脚本：`build_high_quality.py`（另一套 schema 与评估口径）
- 历史评估脚本：`kg_quality_check.py`（预期关系/超边类型与 v3 存在差异）
- 兼容产物：`*_v1v2.json`

说明：当前服务端运行时（`HypergraphClient` + `hypergraph_runtime`）是按“核心类型 + 兼容类型”消费图数据的，不完全等于旧版 `kg_quality_check.py` 的类型预期。

---

## 3. 设计目标与原则

### 3.1 设计目标

- 支撑创新创业项目的“结构化诊断、规则评估、证据追溯、相似项目检索”
- 在教学场景下连接“问题-方法-指标-证据-风险”链路
- 在保证命中率的同时保留解释性（provenance）

### 3.2 设计原则

- 证据优先：节点/关系/超边均带证据字段
- 约束驱动：核心关系类型有明确起点/终点标签约束
- 可兼容演进：引入兼容标签与兼容关系/超边，降低运行时回归风险
- 去重一致性：按 `(label, normalized_name)`、`(type, from, to)`、`(type, sorted_members)` 去重

---

## 4. 数据模型设计

### 4.1 节点设计

`kg_hg_v3` 节点类型分为两类：

- 核心标签（CORE）
  - `Concept`, `Method`, `Task`, `Artifact`, `Metric`, `Case`, `RubricItem`, `Mistake`, `Evidence`, `UserProfile`, `Project`
- 兼容标签（COMPAT）
  - `Market`, `Technology`

节点统一结构（简化）：

```json
{
  "id": "Concept_0001",
  "label": "Concept",
  "properties": {
    "name": "...",
    "description": "...",
    "source": [{"file": "...", "text": "...", "competition": "..."}],
    "schema_version": "kg_hg_v3"
  }
}
```

补充说明：

- `Concept` 会按关键词映射出兼容别名节点 `Market` / `Technology`，并通过 `alias_of` 与 `concept_type` 关联。
- `Evidence` 作为独立节点用于增强解释链路（关系、超边会引用/挂靠证据）。

### 4.2 关系设计

核心关系类型（CORE）：

- `PREREQ`, `USES`, `PRODUCES`, `MEASURED_BY`, `EVIDENCED_BY`, `EVALUATED_BY`, `COMMON_MISTAKE`, `FIX_STRATEGY`, `EXEMPLIFIED_BY`

兼容关系类型（COMPAT）：

- `HAS_MARKET`, `HAS_TECHNOLOGY`, `HAS_TASK`, `HAS_ARTIFACT`, `HAS_METHOD`, `HAS_METRIC`, `HAS_MISTAKE`, `HAS_RUBRIC`

关系字段（简化）：

```json
{
  "id": "REL_000001",
  "type": "USES",
  "from": "Task_0001",
  "to": "Method_0001",
  "properties": {
    "rationale": "...",
    "evidence": [{"file": "...", "text": "...", "competition": "..."}],
    "compatibility": false,
    "schema_version": "kg_hg_v3"
  }
}
```

关系约束（示例）：

- `USES`: `Task -> Method`
- `PRODUCES`: `Task -> Artifact`
- `MEASURED_BY`: `Task|Artifact -> Metric`
- `EVIDENCED_BY`: `非Evidence节点 -> Evidence`

### 4.3 超边设计

核心超边类型（6类）：

- `BusinessModelConsistency`
- `HypothesisEvidenceConclusion`
- `MarketSizingChain`
- `FinancialSelfConsistency`
- `CompetitionScoreMapping`
- `LearningPathUnit`

兼容超边类型：

- `ValueLoop`（由 `BusinessModelConsistency` 派生）
- `RiskPattern`（由 `CompetitionScoreMapping` 派生）

超边字段（简化）：

```json
{
  "id": "HE_BusinessModelConsistency_00001",
  "type": "BusinessModelConsistency",
  "member_node_ids": ["Project_0001", "Concept_0001", "Metric_0001", "Evidence_0001"],
  "properties": {
    "constraints": ["..."],
    "severity": "medium",
    "explanation_template": "...",
    "roles": [{"role": "project", "node_id": "Project_0001", "label": "Project", "name": "..."}],
    "evidence": {"file": "...", "text": "...", "competition": "..."},
    "evidence_list": [{"file": "...", "text": "...", "competition": "..."}],
    "compatibility": false,
    "schema_version": "kg_hg_v3"
  }
}
```

---

## 5. 构建流程设计

### 5.1 主流程（`rebuild_kg_hypergraph_v3.py`）

1. 文档发现：递归扫描 `data/` 下 `.pdf/.docx/.pptx/.txt/.md`
2. 文本抽取：按文件类型选择解析器
3. 上下文压缩：`build_context()` 抽关键词相关句
4. LLM抽取：按统一 prompt 输出 `project/nodes/relations/hyperedges`
5. 标准化与入图：
   - label/type 归一化（alias -> canonical）
   - 关系约束检查
   - 去重合并
   - 证据节点与证据关系挂接
6. 兼容增强：
   - `Concept -> Market/Technology` 兼容节点
   - 项目锚点 `HAS_*`
   - 兼容超边 `ValueLoop/RiskPattern`
7. 图校验：`validate_graph()`
8. 产物写出：根目录、`data/`、`output_v2/` 快照

### 5.2 关键工程机制

- 去重：
  - 节点：`(label, name_key)`
  - 关系：`(type, from, to)`
  - 超边：`(type, sorted(member_ids))`
- 可追溯性：所有对象带来源片段；超边强制挂证据节点
- 兼容开关：通过 `compatibility=true` 标记兼容对象，便于后续治理

---

## 6. 运行时消费与业务评估设计

### 6.1 运行时访问层

- 组件：`backend/apps/hypergraph/hypergraph_client.py`
- 能力：
  - 名称检索与模糊匹配
  - 项目上下文抽取（1-hop）
  - 相似项目检索（Market/Technology 特征 Jaccard）
  - 一致性检查（关键节点/超边覆盖）
  - 文本实体抽取与项目候选推断

### 6.2 诊断与评分链路

- `hypergraph_runtime.py`
  - `build_plan_diagnosis()` 输出一致性告警、缺失节点、风险模式、证据溯源
  - 指标：`label_coverage_rate`, `source_hit_rate`, `explainability_item_rate`, `project_confidence_rate`
- `project_quality.py`
  - 融合规则引擎、rubric 引擎与超图证据基底，产出 `total_score_100`

---

## 7. 评估方法

### 7.1 结构正确性评估（v3原生）

`validate_graph()` 主要检查：

- 关系端点是否存在
- 核心关系是否满足标签约束
- 关系是否具备 evidence
- 超边类型是否合法、成员数>=3、成员是否存在、是否具备 evidence
- 节点 label/name/source 合法性

### 7.2 质量评估（现有离线脚本）

`kg_quality_check.py` 从四个维度打分/告警：

- 完整性：规模、类型覆盖、孤立节点、超边覆盖
- 准确性：必填属性、非法类型、超边成员类型匹配、数值范围
- 连通性：关系度、超边参与度、连通分量、核心节点
- 实用性：Outcome覆盖、Mistake覆盖、方法-概念连接、竞赛相关性

注意：该脚本的“期望类型集”偏旧，与 v3 core/compat 类型不完全一致。

---

## 8. 当前评估结果（数据基线：2026-04-24）

### 8.1 构建产物与过程

- v3重建快照（`output_v2/kg_hg_v3_20260423_235445/rebuild_report.json`）
  - documents_total=103
  - documents_success=101
  - documents_failed=2
  - validation_errors=[]
  - node_count=2689, relation_count=2708, hyperedge_count=717
- 当前根目录增强后数据（`kg_hg_v3`）
  - node=2745, relation=2790, hyperedge=777

### 8.2 证据与兼容指标

- 节点 source 覆盖：100.00%（2745/2745）
- 关系 evidence 覆盖：100.00%（2790/2790）
- 超边 evidence 覆盖：100.00%（777/777）
- 超边包含 Evidence 成员：100.00%（777/777）
- 兼容关系占比：55.73%（1555/2790）
- 兼容超边占比：28.44%（221/777）

### 8.3 `kg_quality_check.py` 实测摘要

执行命令：

```bash
python kg_quality_check.py --nodes kg_nodes.json --relations kg_relations.json --hyperedges hypergraph_edges.json --report quality_report_latest.txt
```

核心结果：

- 节点规模达标：2745 >= 2000
- 孤立节点：333（12.13%）
- 超边节点覆盖：50.89%
- 告警总数：3276

告警构成（关键项）：

- 缺失节点类型：`Outcome`, `Participant`, `Resource`
- 缺失超边类型：`CompetitionShadow`, `PitchLogic`, `ResourceLeverage`
- 非法关系类型：2496
- 非法超边类型：556
- 超边成员类型不匹配：221
- 数值越界：0

### 8.4 告警解释（重点）

高告警并不等于“图不可用”，主要来源于“评估口径不一致”：

- `kg_quality_check.py` 预期旧类型（如 `USES_METHOD`, `HAS_OUTCOME`）
- 当前 v3 使用 `USES`, `PRODUCES`, `HAS_METHOD`, `EVIDENCED_BY` 等新/兼容类型
- v3 强调 `Evidence` 与教学诊断链路；旧评估器未完全吸收该语义

因此当前结论应分两层解读：

- 结构有效性（v3原生校验）：通过
- 旧评估器告警：高（主要是 schema drift，不全是数据质量缺陷）

---

## 9. 风险与改进建议

### 9.1 当前主要风险

- 评估器与 schema 版本漂移，导致质量报告噪声高
- `Project` 的 `competition/stage/milestone` 字段存在空值与非标准化
- 关键业务语义（如 Outcome）在 v3 中弱化，影响旧指标解释性

### 9.2 建议改造（优先级）

1. 新增 `kg_quality_check_v3.py`（高优先）
- 以 v3 `CORE + COMPAT` 类型集为基准
- 兼容对象（`compatibility=true`）独立统计，不与核心对象混算

2. 建立双口径评估（高优先）
- `schema_validity_v3`：结构与约束正确性
- `business_utility_runtime`：命中率、可解释率、诊断覆盖率

3. 加强字段标准化（中优先）
- 统一 `competition/stage/milestone` 枚举
- 对 `Project`、`Metric` 等核心字段做入库前规范化

4. 降低孤立节点（中优先）
- 针对孤立节点补充桥接关系（尤其 Project 与 Method/Metric/Market）
- 为高价值节点增加 hyperedge 参与

5. 增量回归监控（中优先）
- 每次重建输出固定 KPI：
  - 结构错误数
  - source/evidence 覆盖率
  - 孤立率
  - 兼容对象占比
  - 运行时诊断命中率

---

## 10. 复现命令

### 10.1 重建 v3 图谱

```bash
python scripts/rebuild_kg_hypergraph_v3.py --project-root . --data-dir data
```

### 10.2 执行现有离线评估

```bash
python kg_quality_check.py --nodes kg_nodes.json --relations kg_relations.json --hyperedges hypergraph_edges.json --report quality_report_latest.txt
```

### 10.3 查看构建报告

- `output_v2/*/rebuild_report.json`
- `output_v2/*/extraction_log.json`

---

## 11. 结论

- 本项目 KG/HG 采用“核心 schema + 兼容层 + 强证据追溯”的工程化设计，能够支撑运行时诊断与评分。
- 当前 v3 产物在结构完整性与可追溯性上表现稳定。 
- 当前离线质量告警偏高的主因是评估器与 schema 版本不一致。下一阶段应优先完成 v3 评估器对齐，以获得可解释、可行动的质量结论。
