# API Contract (RESTful)

Base URL: `/api`

Response envelope:

```json
{
  "code": 200,
  "message": "ok",
  "data": {}
}
```

## Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/profile`
- `PUT /auth/profile`

## AI

- `POST /ai/chat` 学生端引导提问
- `POST /ai/validate` 学生端逻辑验证
- `POST /agent/roadmap-simulate` 路演模拟（开场、逐题评分、报告）
- `POST /agent/competition-advise` 竞赛辅导与分项评分建议
- `POST /agent/tutor` 知识点讲解与实践任务生成
- `POST /agent/case-recall` 向量召回优秀案例（P3）
- `POST /agent/workflow-orchestrate` 多智能体编排工作流（P3）
- `POST /reviews/generate` 批阅生成（学生/教师角色差异化）
- `PUT /reviews/{id}` 教师编辑批阅建议

## Plans

- `POST /plans/upload` PDF上传
- `GET /plans` 方案列表（学生看自己，教师看已绑定学生）
- `POST /plans/{id}/submit` 学生提交到教师
- `GET /plans/{id}/reviews` 方案批阅记录
- `GET /project/{id}/bottleneck` 项目瓶颈诊断（项目教练Agent）
- `GET /project/{id}/rubric-score` Rubric逐项评分明细
- `GET /project/{id}/evidence-chain` 证据链追溯
- `GET /project/{id}/potential-report` 项目潜力评估报告
- `GET /project/{id}/hypergraph-reasoning` 超图推理与失败路径建议
- `GET /history` 对话/方案/批阅历史

## Mentorship

- `GET /teachers` 教师搜索
- `POST /mentorship/apply` 学生提交申请
- `GET /mentorship/applications` 学生/教师申请列表
- `POST /mentorship/{id}/audit` 教师审核

## Teacher

- `GET /teacher/dashboard` 看板数据
- `GET /teacher/rubrics` 评分维度配置
- `GET /teacher/case-library-summary` 案例库概览
- `GET /teacher/prompt-scenes` 场景提示词配置
- `GET /teacher/common-issues` 共性问题
- `GET /teacher/class-radar` 班级Rubric能力雷达图数据
- `GET /teacher/metrics-stream` 指标流（聚合+雷达，支持分页/筛选）
- `GET /teacher/class-learning-report` 班级学情报告（能力矩阵+教学建议）
- `GET /teacher/common-mistakes` 规则触发高频Top5
- `GET /teacher/high-risk-projects` 高风险项目列表
- `GET /teacher/knowledge-recommendations` 知识点推荐
- `POST /teacher/intervention` 教师干预（强制追问点/规则覆盖）
- `POST /teacher/ai-chat` 教师上下文AI对话

## Hypergraph

- `POST /hypergraph/import-case` 导入案例与超边到Neo4j（Neo4j关闭时返回降级状态）

### Teacher payload keys

- `GET /teacher/dashboard`
  - `metrics`: `student_count`, `plan_count`, `submission_rate`, `optimization_rate`, `case_library_count`, `synthetic_case_count`
  - `chart`: `indicators`, `avg_scores`, `submission_trend`, `weights`
- `GET /teacher/rubrics`
  - item: `code`, `label`, `weight`, `scoring_standard`, `prompt_hint`
- `GET /teacher/case-library-summary`
  - `total`, `synthetic`, `industry_stats`, `latest_items[]`
- `GET /teacher/prompt-scenes`
  - item: `scene_key`, `scene_name`, `fixed_prompt`, `scene_prompts`, `output_schema`

### Review generation payload keys

- `POST /reviews/generate`
  - request: `plan_id`, `audience_role` (`student|teacher`)
  - response item: `issues[]`, `annotations[]`, `guidance_questions[]`, `examples[]`, `suggestions[]`, `summary`, `review_meta.dimension_scores[]`

## Messages

- `GET /messages` 消息通知
  - returns `{ items, timezone: "UTC+8", format: "YYYY-MM-DD HH:MM:SS" }`

## List Query Conventions

- 通用分页参数：`page`、`page_size`（返回 `items` + `total`）
- 通用筛选参数：`q`（关键词），`status`（状态/来源）
- 已统一支持分页模式的接口：`GET /plans`、`GET /messages`、`GET /history?mode=stream`、`GET /teacher/metrics-stream`
- 新增支持分页模式的接口：`GET /teachers`、`GET /mentorship/applications`、`GET /plans/{id}/reviews`
  `GET /teacher/prompt-scenes`、`GET /teacher/common-issues`、`GET /teacher/high-risk-projects`
