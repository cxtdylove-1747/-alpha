from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from ..models import MentorshipRelation, Plan
from .project_quality import evaluate_project_quality


def build_class_learning_report(teacher) -> Dict[str, Any]:
    student_ids = list(MentorshipRelation.objects.filter(teacher=teacher).values_list("student_id", flat=True))
    plans = list(Plan.objects.filter(student_id__in=student_ids, status=Plan.STATUS_SUBMITTED))

    rubric_bucket: Dict[str, List[float]] = defaultdict(list)
    risk_projects = []
    interventions = []

    for plan in plans[:200]:
        quality = evaluate_project_quality(plan)
        for row in quality.get("rubric") or []:
            rubric_bucket[row.get("rubric_id")].append(float(row.get("score") or 0))

        high_rules = [item for item in (quality.get("triggered_rules") or []) if item.get("severity") == "high"]
        if high_rules:
            risk_projects.append(
                {
                    "project_id": plan.id,
                    "project_name": plan.title,
                    "student_name": plan.student.username,
                    "high_rules": [x.get("rule_id") for x in high_rules],
                }
            )
            interventions.append(
                {
                    "project_id": plan.id,
                    "action": "安排教师一对一答辩追问，优先修复高风险规则。",
                }
            )

    ability_matrix = {
        key: round(sum(values) / len(values), 2) if values else 0.0
        for key, values in rubric_bucket.items()
    }

    return {
        "teacher": teacher.username,
        "student_count": len(set(student_ids)),
        "project_count": len(plans),
        "ability_matrix": ability_matrix,
        "high_risk_projects": risk_projects[:20],
        "teaching_suggestions": interventions[:20],
    }

