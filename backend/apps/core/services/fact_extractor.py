from __future__ import annotations

import re
from typing import Any, Dict


def _extract_money(text: str, keyword: str, fallback: float = 0) -> float:
    match = re.search(rf"{keyword}[^0-9]{{0,8}}([0-9]+(?:\.[0-9]+)?)", text, flags=re.IGNORECASE)
    if not match:
        return fallback
    try:
        return float(match.group(1))
    except Exception:
        return fallback


def extract_facts(text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    body = (text or "").strip()
    meta = metadata or {}
    interview_count = len(re.findall(r"访谈", body))
    survey_count = len(re.findall(r"问卷", body))

    facts = {
        "customer_segment": meta.get("customer_segment") or ("学生" if "学生" in body else "未定义"),
        "value_proposition_target": meta.get("value_proposition_target") or ("学生" if "学生" in body else "未定义"),
        "channel": meta.get("channel") or ("微信" if "微信" in body else "线下"),
        "customer_reachable_channels": meta.get("customer_reachable_channels") or ["微信", "校园BBS"],
        "has_willingness_to_pay_evidence": bool(re.search(r"付费意愿|支付意愿|预付", body)),
        "tam": _extract_money(body, "TAM", float(meta.get("tam") or 0)),
        "sam": _extract_money(body, "SAM", float(meta.get("sam") or 0)),
        "som": _extract_money(body, "SOM", float(meta.get("som") or 0)),
        "user_interview_count": int(meta.get("user_interview_count") or interview_count),
        "survey_sample": int(meta.get("survey_sample") or survey_count * 10),
        "competitor_analysis": {
            "has_feature_comparison": bool(re.search(r"竞品|对比矩阵|功能对比", body)),
        },
        "innovation_claim": {
            "has_verifiable_metric": bool(re.search(r"转化率|留存率|NPS|准确率|可验证", body)),
        },
        "ltv": _extract_money(body, "LTV", float(meta.get("ltv") or 0)),
        "cac": _extract_money(body, "CAC", float(meta.get("cac") or 0)),
        "growth_strategy_missing_retention": not bool(re.search(r"留存|复购|活跃", body)),
        "any_milestone_without_resource": not bool(re.search(r"里程碑.*(预算|人力|时间)|资源", body)),
        "involves_data_privacy": bool(re.search(r"隐私|数据采集|人脸|医疗", body)),
        "has_compliance_plan": bool(re.search(r"合规|授权|脱敏|备案", body)),
        "tech_trl": float(meta.get("tech_trl") or 2),
        "required_funding": float(meta.get("required_funding") or _extract_money(body, "融资", 0)),
        "available_budget": float(meta.get("available_budget") or _extract_money(body, "预算", 0)),
        "mvp_test_has_no_success_metric": not bool(re.search(r"成功指标|验收标准|KPI", body)),
        "pitch_deck_has_story_gap": not bool(re.search(r"问题.*方案.*证据.*商业", body, flags=re.S)),
        "rubric_evidence_provided": float(meta.get("rubric_evidence_provided") or (interview_count + survey_count)),
        "required_evidence": float(meta.get("required_evidence") or 5),
    }
    return facts

