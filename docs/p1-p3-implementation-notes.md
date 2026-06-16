# P1-P3 Implementation Notes

## What Was Added

- P1 agents:
  - `POST /api/agent/roadmap-simulate`
  - `POST /api/agent/competition-advise`
  - `POST /api/agent/tutor`
- P2 reports and analytics:
  - `GET /api/project/{id}/potential-report`
  - `GET /api/teacher/class-learning-report`
  - teacher analytics page wiring in `frontend/src/pages/teacher/LearningAnalytics.vue`
- P3 advanced capabilities (degradable implementation):
  - `POST /api/agent/case-recall`
  - `POST /api/agent/workflow-orchestrate`
  - `GET /api/project/{id}/hypergraph-reasoning`

## Runtime Notes

- Vector retrieval supports `faiss` mode when `faiss-cpu + numpy` are installed, and auto-falls back to token-frequency cosine.
- LangGraph workflow supports real `StateGraph` when `langgraph` is installed, and auto-falls back to sequential orchestration.
- Hypergraph reasoning uses Neo4j when enabled; otherwise returns rule-based fallback insights.
- Hypergraph bulk import command: `python manage.py import_hypergraph_from_case_library --limit 200`.

## Quick Verify

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体\backend"
python manage.py check
python manage.py test apps.core.tests -v 1
python scripts/smoke_test.py
Pop-Location
```

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体\frontend"
npm run build
Pop-Location
```


