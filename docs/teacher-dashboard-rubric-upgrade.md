# Teacher Dashboard + Rubric Upgrade

## What was added

### Backend

- Student rubric detail enriched with:
  - 9-dimension ability profile (`ability_profile`)
  - highest-severity triggered rule (`top_risk_rule`)
  - one-line recommendation (`improvement_tip`)
- New teacher aggregate APIs:
  - `GET /api/teacher/aggregate-dashboard`
  - `GET /api/teacher/rule-drilldown?rule_id=H5`
  - `GET /api/teacher/project/{plan_id}/evidence-detail`
- Demo seeding command:
  - `python manage.py seed_class_demo_projects`
  - creates `student1`, `student2`, `student3`
  - creates/submits 3 project plans as `.docx` files

### Frontend

- Student `PlanManager` now displays:
  - ability profile table (R1-R9 mapped to V2 names)
  - highlighted top-risk rule
  - improvement tip
- Teacher `LearningAnalytics` redesigned:
  - class summary cards
  - interactive rule heatmap table
  - class radar
  - two-level evidence drilldown dialogs

## Runbook

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体\backend"
python manage.py seed_quality_baseline
python manage.py seed_class_demo_projects
python manage.py test apps.core.tests -v 1
python scripts/run_teacher_student_acceptance.py
Pop-Location
```

```powershell
Push-Location "C:\Users\Admin\PycharmProjects\智能体\frontend"
npm run build
Pop-Location
```

## Acceptance expectations

- `teacher_rule_heatmap_rows` should be `15`.
- Student rubric detail should contain `ability_profile` (9 dimensions).
- Student rubric detail should contain `top_risk_rule`.
- Drilldown endpoints return project/rule evidence arrays.

