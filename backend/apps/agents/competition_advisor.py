from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from ..core.services.llm_gateway import call_llm


@dataclass(frozen=True)
class RubricDimension:
    dimension: str
    weight: float
    max_score: float
    focus: str
    keywords: tuple[str, ...]
    evidence_required: tuple[str, ...]
    advice_template: str


COMPETITION_RUBRICS: dict[str, list[RubricDimension]] = {
    "挑战杯": [
        RubricDimension(
            dimension="创新性与问题洞察",
            weight=0.22,
            max_score=20,
            focus="innovation",
            keywords=("创新", "痛点", "差异化", "替代方案", "护城河", "首创", "value proposition", "moat"),
            evidence_required=("用户访谈", "问题量化", "替代方案对比"),
            advice_template="补充用户真实痛点证据，并明确与主流方案的差异边界。",
        ),
        RubricDimension(
            dimension="社会价值与落地意义",
            weight=0.18,
            max_score=20,
            focus="social_value",
            keywords=("社会价值", "公益", "就业", "双碳", "乡村", "公共服务", "影响力"),
            evidence_required=("受益人画像", "效果指标", "试点反馈"),
            advice_template="补充社会影响指标（覆盖人数、改善幅度）与试点场景反馈。",
        ),
        RubricDimension(
            dimension="技术/方案可行性",
            weight=0.2,
            max_score=20,
            focus="feasibility",
            keywords=("原型", "MVP", "验证", "技术路线", "流程", "实施", "迭代"),
            evidence_required=("阶段里程碑", "关键风险应对", "资源匹配"),
            advice_template="拆解技术路径并补充里程碑、资源配置与风险应对方案。",
        ),
        RubricDimension(
            dimension="商业模式与持续性",
            weight=0.16,
            max_score=20,
            focus="business",
            keywords=("商业模式", "收入", "成本", "现金流", "定价", "LTV", "CAC", "复购"),
            evidence_required=("收入模型", "成本结构", "增长路径"),
            advice_template="明确付费对象与定价逻辑，给出单位经济模型与增长节奏。",
        ),
        RubricDimension(
            dimension="团队与执行能力",
            weight=0.14,
            max_score=10,
            focus="team",
            keywords=("团队", "分工", "执行", "里程碑", "合作方", "资源"),
            evidence_required=("成员能力矩阵", "关键分工", "外部资源"),
            advice_template="补齐团队能力矩阵与阶段责任人，增强执行可信度。",
        ),
        RubricDimension(
            dimension="路演表达与答辩",
            weight=0.1,
            max_score=10,
            focus="presentation",
            keywords=("路演", "答辩", "故事线", "逻辑", "可视化", "证据链"),
            evidence_required=("核心结论页", "关键数据页", "问答预案"),
            advice_template="优化路演叙事顺序，形成“结论-证据-行动”的答辩结构。",
        ),
    ],
    "大创": [
        RubricDimension(
            dimension="研究基础与问题定义",
            weight=0.2,
            max_score=20,
            focus="research",
            keywords=("文献", "研究现状", "问题定义", "研究目标", "研究价值", "假设"),
            evidence_required=("文献综述", "研究问题边界", "目标指标"),
            advice_template="补充文献对比与研究问题边界，明确可验证目标。",
        ),
        RubricDimension(
            dimension="研究方法与实验设计",
            weight=0.22,
            max_score=20,
            focus="method",
            keywords=("研究方法", "实验", "样本", "对照组", "问卷", "访谈", "数据分析"),
            evidence_required=("样本与方法说明", "实验流程", "统计方法"),
            advice_template="补足样本来源、实验流程和统计方法，提升方法可靠性。",
        ),
        RubricDimension(
            dimension="实施方案与进度管理",
            weight=0.18,
            max_score=20,
            focus="execution",
            keywords=("实施方案", "计划", "进度", "里程碑", "阶段成果", "风险控制"),
            evidence_required=("月度进度表", "阶段目标", "风险应对"),
            advice_template="按月拆解里程碑并绑定可交付成果与风险预案。",
        ),
        RubricDimension(
            dimension="成果质量与创新贡献",
            weight=0.18,
            max_score=20,
            focus="outcome",
            keywords=("成果", "论文", "专利", "原型", "创新点", "推广价值"),
            evidence_required=("成果产出物", "创新点说明", "验证结果"),
            advice_template="明确成果形态和创新贡献，补齐结果验证证据。",
        ),
        RubricDimension(
            dimension="预算与资源配置",
            weight=0.12,
            max_score=10,
            focus="budget",
            keywords=("预算", "经费", "设备", "材料", "资源配置", "投入产出"),
            evidence_required=("预算明细", "资源来源", "费用合理性说明"),
            advice_template="细化预算分项并说明费用与研究目标的对应关系。",
        ),
        RubricDimension(
            dimension="答辩表达与规范性",
            weight=0.1,
            max_score=10,
            focus="presentation",
            keywords=("答辩", "表达", "规范", "结构", "引用", "伦理"),
            evidence_required=("答辩脚本", "引用规范", "伦理说明"),
            advice_template="优化答辩结构并补齐引用、伦理与格式规范说明。",
        ),
    ],
    "互联网+": [
        RubricDimension(
            dimension="市场机会与用户价值",
            weight=0.2,
            max_score=20,
            focus="market",
            keywords=("市场规模", "用户需求", "细分市场", "痛点", "增长空间", "TAM", "SAM", "SOM"),
            evidence_required=("市场测算", "目标用户画像", "需求验证"),
            advice_template="补充市场测算逻辑与用户需求验证证据。",
        ),
        RubricDimension(
            dimension="产品方案与创新性",
            weight=0.2,
            max_score=20,
            focus="product",
            keywords=("产品", "创新", "差异化", "功能", "体验", "MVP", "迭代"),
            evidence_required=("产品原型", "核心创新点", "迭代计划"),
            advice_template="展示产品原型和创新对比，给出迭代路径。",
        ),
        RubricDimension(
            dimension="商业化与增长模型",
            weight=0.24,
            max_score=20,
            focus="business",
            keywords=("商业模式", "收入", "成本", "获客", "留存", "复购", "LTV", "CAC", "ROI"),
            evidence_required=("收入结构", "获客路径", "单位经济模型"),
            advice_template="补足获客-转化-留存链路，量化单位经济模型。",
        ),
        RubricDimension(
            dimension="运营执行与资源协同",
            weight=0.14,
            max_score=20,
            focus="operation",
            keywords=("运营", "渠道", "伙伴", "供应链", "执行", "里程碑", "资源"),
            evidence_required=("运营计划", "渠道策略", "关键合作资源"),
            advice_template="明确运营策略、渠道分层和关键资源协同方式。",
        ),
        RubricDimension(
            dimension="团队能力与组织韧性",
            weight=0.12,
            max_score=10,
            focus="team",
            keywords=("团队", "分工", "核心成员", "经验", "组织", "执行力"),
            evidence_required=("核心成员履历", "职责分工", "组织机制"),
            advice_template="补齐团队履历与分工机制，强化执行韧性。",
        ),
        RubricDimension(
            dimension="路演表达与资本沟通",
            weight=0.1,
            max_score=10,
            focus="presentation",
            keywords=("路演", "融资", "投资人", "答辩", "逻辑", "数据页"),
            evidence_required=("核心数据页", "融资用途", "问答预案"),
            advice_template="强化投资人视角叙事，补齐融资逻辑与关键数据页。",
        ),
    ],
}

COMPETITION_ALIASES = {
    "挑战杯": "挑战杯",
    "挑战杯竞赛": "挑战杯",
    "大创": "大创",
    "大学生创新创业训练计划": "大创",
    "互联网+": "互联网+",
    "互联网＋": "互联网+",
}

WINNING_REFERENCE = {
    "挑战杯": "参考往届高分项目：问题证据充分、社会价值量化、实施路径清晰。",
    "大创": "参考高质量大创立项书：研究问题明确、方法可复现、阶段成果可量化。",
    "互联网+": "参考高分互联网+项目：市场测算完整、单位经济模型清楚、增长路径可执行。",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _parse_json_text(content: str) -> Dict[str, Any] | None:
    raw = str(content or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _score_bucket(score_ratio: float) -> str:
    if score_ratio >= 0.76:
        return "strong"
    if score_ratio >= 0.52:
        return "medium"
    return "weak"


def _keyword_hit_ratio(text: str, keywords: tuple[str, ...]) -> float:
    if not keywords:
        return 0.0
    normalized = _norm_text(text)
    hit = 0
    for kw in keywords:
        key = _norm_text(kw)
        if key and key in normalized:
            hit += 1
    return hit / len(keywords)


def _extract_hypergraph_signal(hypergraph_context: Dict[str, Any] | None) -> Dict[str, float]:
    ctx = hypergraph_context or {}
    metrics = ctx.get("metrics") or {}
    source_hit = _safe_float(metrics.get("source_hit_rate"), 0.55)
    explainability = _safe_float(metrics.get("explainability_item_rate"), 0.55)
    confidence = _safe_float(metrics.get("project_confidence_rate"), 0.55)
    coverage = _safe_float(metrics.get("label_coverage_rate"), 0.55)
    risk_rows = _safe_list(ctx.get("risk_patterns"))
    risk_penalty = min(0.18, len(risk_rows) * 0.035)
    quality = _clamp((source_hit * 0.28) + (explainability * 0.28) + (confidence * 0.24) + (coverage * 0.2), 0.25, 0.98)
    return {
        "source_hit": _clamp(source_hit, 0.0, 1.0),
        "explainability": _clamp(explainability, 0.0, 1.0),
        "confidence": _clamp(confidence, 0.0, 1.0),
        "coverage": _clamp(coverage, 0.0, 1.0),
        "quality": quality,
        "risk_penalty": risk_penalty,
    }


def _normalize_competition(name: str) -> str:
    value = str(name or "").strip()
    return COMPETITION_ALIASES.get(value, value if value in COMPETITION_RUBRICS else "挑战杯")


def _normalize_project_type(project_type: str) -> str:
    value = str(project_type or "").strip().lower()
    if value in {"commercial", "public_welfare"}:
        return value
    return "auto"


def _compose_summary_markdown(data: Dict[str, Any]) -> str:
    rows = _safe_list(data.get("dimension_scores"))
    top_actions = _safe_list(data.get("prioritized_actions"))[:3]
    lines = [
        f"### 评分结论（{data.get('competition', '竞赛')}）",
        "",
        f"- 总分预估：**{data.get('total_score_estimate', 0)}/100**",
        f"- 项目类型：`{data.get('project_type', 'auto')}`",
        "",
        "| 维度 | 得分 | 权重 | 关键判断 |",
        "| --- | --- | --- | --- |",
    ]
    for item in rows:
        lines.append(
            f"| {item.get('dimension', '-')} | {item.get('score', 0)}/{item.get('max_score', 0)} | "
            f"{item.get('weight_percent', 0)}% | {str(item.get('rationale', '-'))[:42]} |"
        )
    if top_actions:
        lines.extend(["", "### 优先优化动作"])
        for idx, action in enumerate(top_actions, start=1):
            lines.append(f"{idx}. {action.get('action', '-')}: {action.get('reason', '-')}")
    return "\n".join(lines)


class CompetitionAdvisor:
    scoring_version = "competition_rubric_v2"

    def advise(
        self,
        competition: str,
        text: str,
        project_type: str = "auto",
        hypergraph_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        normalized_competition = _normalize_competition(competition)
        normalized_project_type = _normalize_project_type(project_type)
        rubrics = COMPETITION_RUBRICS[normalized_competition]
        heuristic = self._heuristic_advise(
            competition=normalized_competition,
            project_type=normalized_project_type,
            text=text,
            rubrics=rubrics,
            hypergraph_context=hypergraph_context,
        )
        llm_result = self._advise_by_llm(
            competition=normalized_competition,
            project_type=normalized_project_type,
            text=text,
            rubrics=rubrics,
            hypergraph_context=hypergraph_context,
        )
        return self._merge_result(heuristic=heuristic, llm_result=llm_result)

    def _heuristic_advise(
        self,
        competition: str,
        project_type: str,
        text: str,
        rubrics: list[RubricDimension],
        hypergraph_context: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        plan_text = str(text or "")[:12000]
        signal = _extract_hypergraph_signal(hypergraph_context)
        dimensions: list[dict[str, Any]] = []
        all_gaps: list[str] = []

        for dim in rubrics:
            ratio = _keyword_hit_ratio(plan_text, dim.keywords)
            base = 0.3 + (ratio * 0.48) + (signal["quality"] * 0.24) - signal["risk_penalty"]
            if dim.focus in {"business", "market"}:
                base += (signal["confidence"] - 0.55) * 0.16
            if dim.focus in {"research", "method", "social_value"}:
                base += (signal["source_hit"] - 0.55) * 0.14
            if dim.focus in {"presentation", "team"}:
                base += (signal["explainability"] - 0.55) * 0.12
            score_ratio = _clamp(base, 0.18, 0.98)
            score = round(score_ratio * dim.max_score, 2)
            weighted = round((score / dim.max_score) * dim.weight * 100, 2)

            normalized_text = _norm_text(plan_text)
            missing_evidence = [x for x in dim.evidence_required if _norm_text(x) not in normalized_text]
            if score_ratio < 0.56 and missing_evidence:
                all_gaps.extend(missing_evidence[:2])

            dimensions.append(
                {
                    "dimension": dim.dimension,
                    "criterion": dim.dimension,
                    "focus": dim.focus,
                    "weight": round(dim.weight * 100, 2),
                    "weight_percent": round(dim.weight * 100, 2),
                    "max_score": dim.max_score,
                    "score": score,
                    "weighted_score": weighted,
                    "evidence_strength": _score_bucket(score_ratio),
                    "missing_evidence": missing_evidence[:3],
                    "rationale": f"关键词命中率 {round(ratio * 100)}%，结合超图质量信号评估为 {round(score, 1)} 分。",
                    "optimization_suggestion": dim.advice_template,
                }
            )

        total_score = round(sum(item["weighted_score"] for item in dimensions), 2)
        strengths = [
            f"{item['dimension']}：{item['score']}/{item['max_score']}"
            for item in sorted(dimensions, key=lambda row: row["weighted_score"], reverse=True)[:3]
            if (_safe_float(item.get("score")) / max(_safe_float(item.get("max_score")), 1)) >= 0.7
        ]
        if not strengths:
            strengths = [f"{dimensions[0]['dimension']}具备一定基础，建议继续强化证据化表达。"] if dimensions else []

        risk_alerts: list[str] = []
        for row in _safe_list((hypergraph_context or {}).get("risk_patterns"))[:4]:
            risk_alerts.append(f"{row.get('type') or '风险项'}（{row.get('severity') or '中'}）")
        if signal["confidence"] < 0.45:
            risk_alerts.append("超图项目匹配置信度偏低，建议先补齐项目核心定义与证据链。")
        if signal["explainability"] < 0.45:
            risk_alerts.append("可解释项覆盖偏低，建议增加关键结论的来源与佐证。")

        low_dims = sorted(
            dimensions,
            key=lambda row: (_safe_float(row.get("score")) / max(_safe_float(row.get("max_score")), 1)),
        )[:3]
        actions = []
        for idx, row in enumerate(low_dims, start=1):
            actions.append(
                {
                    "priority": idx,
                    "dimension": row.get("dimension"),
                    "action": row.get("optimization_suggestion"),
                    "reason": f"当前得分 {row.get('score')}/{row.get('max_score')}，低于该维度期望水平。",
                }
            )

        result = {
            "competition": competition,
            "project_type": project_type,
            "scoring_version": self.scoring_version,
            "total_score": total_score,
            "total_score_estimate": total_score,
            "dimension_scores": dimensions,
            "strengths": strengths,
            "evidence_gaps": list(dict.fromkeys(all_gaps))[:8],
            "risk_alerts": risk_alerts,
            "prioritized_actions": actions,
            "winning_case_reference": WINNING_REFERENCE.get(competition, ""),
            "summary": "",
            "summary_markdown": "",
        }
        result["summary_markdown"] = _compose_summary_markdown(result)
        result["summary"] = result["summary_markdown"]
        return result

    def _advise_by_llm(
        self,
        competition: str,
        project_type: str,
        text: str,
        rubrics: list[RubricDimension],
        hypergraph_context: Dict[str, Any] | None,
    ) -> Dict[str, Any] | None:
        rubric_payload = [
            {
                "dimension": item.dimension,
                "weight_percent": round(item.weight * 100, 2),
                "max_score": item.max_score,
                "focus": item.focus,
            }
            for item in rubrics
        ]
        hypergraph_payload = {
            "metrics": (hypergraph_context or {}).get("metrics") or {},
            "risk_patterns": _safe_list((hypergraph_context or {}).get("risk_patterns"))[:4],
            "suggested_evidence": _safe_list((hypergraph_context or {}).get("suggested_evidence"))[:6],
        }
        prompt = (
            "请扮演高校竞赛评委，基于给定评分维度输出严格 JSON。"
            "必须返回字段：competition, project_type, total_score_estimate, dimension_scores, strengths, evidence_gaps, "
            "risk_alerts, prioritized_actions, winning_case_reference, summary_markdown。"
            "dimension_scores 每项包含：dimension, weight, max_score, score, weighted_score, rationale, optimization_suggestion, missing_evidence。"
            f"\n竞赛：{competition}\n项目类型：{project_type}"
            f"\n评分维度：{json.dumps(rubric_payload, ensure_ascii=False)}"
            f"\n超图上下文：{json.dumps(hypergraph_payload, ensure_ascii=False)}"
            f"\n项目材料：{str(text or '')[:8000]}"
        )
        system = (
            "你是严谨的创新创业竞赛评委。"
            "评分要给出依据，不要空泛套话。"
            "输出必须是合法 JSON，不要包含 markdown 代码块。"
        )
        content = call_llm(prompt=prompt, system_prompt=system, temperature=0.2, timeout_seconds=0)
        if not content:
            return None
        return _parse_json_text(content)

    def _merge_result(self, heuristic: Dict[str, Any], llm_result: Dict[str, Any] | None) -> Dict[str, Any]:
        if not llm_result:
            return heuristic

        merged = dict(heuristic)
        merged.update({k: v for k, v in llm_result.items() if v not in (None, "", [])})

        llm_dimensions = _safe_list(merged.get("dimension_scores"))
        if not llm_dimensions:
            merged["dimension_scores"] = heuristic["dimension_scores"]
        else:
            normalized = []
            heur_map = {item["dimension"]: item for item in heuristic["dimension_scores"]}
            for row in llm_dimensions:
                name = str(row.get("dimension") or row.get("criterion") or "").strip()
                base = heur_map.get(name, {})
                max_score = _safe_float(row.get("max_score"), _safe_float(base.get("max_score"), 10))
                score = _safe_float(row.get("score"), _safe_float(base.get("score"), 0))
                weight_percent = _safe_float(row.get("weight"), _safe_float(base.get("weight"), _safe_float(base.get("weight_percent"), 0)))
                weighted_score = _safe_float(row.get("weighted_score"), round((score / max(max_score, 1)) * weight_percent, 2))
                normalized.append(
                    {
                        "dimension": name or base.get("dimension") or "未命名维度",
                        "criterion": name or base.get("criterion") or "未命名维度",
                        "focus": row.get("focus") or base.get("focus") or "",
                        "weight": round(weight_percent, 2),
                        "weight_percent": round(weight_percent, 2),
                        "max_score": round(max_score, 2),
                        "score": round(score, 2),
                        "weighted_score": round(weighted_score, 2),
                        "evidence_strength": row.get("evidence_strength") or base.get("evidence_strength") or "medium",
                        "missing_evidence": _safe_list(row.get("missing_evidence") or base.get("missing_evidence")),
                        "rationale": str(row.get("rationale") or base.get("rationale") or "").strip(),
                        "optimization_suggestion": str(
                            row.get("optimization_suggestion")
                            or row.get("suggestion")
                            or base.get("optimization_suggestion")
                            or ""
                        ).strip(),
                    }
                )
            merged["dimension_scores"] = normalized

        if not _safe_float(merged.get("total_score_estimate")):
            merged["total_score_estimate"] = round(sum(_safe_float(x.get("weighted_score")) for x in merged["dimension_scores"]), 2)
        if not _safe_float(merged.get("total_score")):
            merged["total_score"] = merged["total_score_estimate"]

        merged["competition"] = merged.get("competition") or heuristic.get("competition")
        merged["project_type"] = merged.get("project_type") or heuristic.get("project_type")
        merged["scoring_version"] = self.scoring_version
        merged["strengths"] = _safe_list(merged.get("strengths")) or heuristic.get("strengths", [])
        merged["evidence_gaps"] = _safe_list(merged.get("evidence_gaps")) or heuristic.get("evidence_gaps", [])
        merged["risk_alerts"] = _safe_list(merged.get("risk_alerts")) or heuristic.get("risk_alerts", [])
        merged["prioritized_actions"] = _safe_list(merged.get("prioritized_actions")) or heuristic.get("prioritized_actions", [])
        merged["winning_case_reference"] = str(
            merged.get("winning_case_reference") or heuristic.get("winning_case_reference") or ""
        ).strip()

        if not str(merged.get("summary_markdown") or "").strip():
            merged["summary_markdown"] = _compose_summary_markdown(merged)
        if not str(merged.get("summary") or "").strip():
            merged["summary"] = merged["summary_markdown"]
        return merged
