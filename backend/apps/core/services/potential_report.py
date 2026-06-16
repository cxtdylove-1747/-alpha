from __future__ import annotations

from typing import Any, Dict

from .project_quality import evaluate_project_quality
from .vector_retrieval import VectorRetrievalService


def build_potential_report(plan) -> Dict[str, Any]:
    quality = evaluate_project_quality(plan)
    total = float(quality.get("total_score_100") or 0)

    radar = {
        "problem": _score_of(quality, "R1"),
        "evidence": _score_of(quality, "R2"),
        "feasibility": _score_of(quality, "R3"),
        "business": _score_of(quality, "R4"),
        "innovation": _score_of(quality, "R7"),
    }

    retrieval = VectorRetrievalService().recall_cases(plan.extracted_text or plan.title, top_k=3)
    industry_benchmark = retrieval[0]["industry"] if retrieval else "未知"

    suggestions = [
        "优先修复所有 high 级规则，再进行路演演练。",
        "补充原文证据链（访谈、问卷、指标）提升评审可信度。",
        "结合同赛道优秀案例调整商业闭环叙事。",
    ]

    level = "高潜力" if total >= 80 else "中潜力" if total >= 60 else "待提升"

    return {
        "project_id": plan.id,
        "project_name": plan.title,
        "potential_level": level,
        "total_score_100": total,
        "radar": radar,
        "industry_benchmark": industry_benchmark,
        "reference_cases": retrieval,
        "suggestions": suggestions,
    }


def _score_of(quality: Dict[str, Any], rubric_id: str) -> float:
    for item in quality.get("rubric") or []:
        if item.get("rubric_id") == rubric_id:
            return float(item.get("score") or 0)
    return 0.0

