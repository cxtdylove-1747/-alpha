from __future__ import annotations

from typing import Any, Dict

from ...hypergraph.neo4j_client import get_neo4j_client
from .project_quality import evaluate_project_quality
from .graph_observability import track_graph_call


def infer_project_paths(plan) -> Dict[str, Any]:
    client = get_neo4j_client()
    risk_hyperedges = []
    tech_failure_paths = []

    if client.enabled:
        risk_hyperedges = client.project_risk_hyperedges(str(plan.id))
        for keyword in ["AI", "机器学习", "数据"]:
            tech_failure_paths.extend(client.failure_cases_by_technology(keyword))

    quality = evaluate_project_quality(plan)
    high_rules = [item for item in quality.get("triggered_rules") or [] if item.get("severity") == "high"]

    result = {
        "neo4j_enabled": client.enabled,
        "risk_hyperedges": risk_hyperedges,
        "failure_paths": tech_failure_paths[:10],
        "rule_risk_summary": high_rules,
        "recommendation": "优先修复高风险规则并对照失败路径补强防御策略。",
    }
    track_graph_call(
        graph_type="hypergraph",
        operation="infer_project_paths",
        source="project_reasoning",
        success=bool(client.enabled),
        user_id=getattr(plan, "student_id", None),
        plan_id=getattr(plan, "id", None),
        detail={
            "neo4j_enabled": bool(client.enabled),
            "risk_hyperedge_count": len(risk_hyperedges),
            "failure_path_count": len(result.get("failure_paths") or []),
            "high_rule_count": len(high_rules),
        },
    )
    return result

