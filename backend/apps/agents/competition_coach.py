from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from ..core.services.hypergraph_preview import build_preview_graph
from ..core.services.llm_gateway import call_llm


def _normalize_project_type(project_type: str) -> str:
    value = str(project_type or "").strip().lower()
    if value in {"public_welfare", "public", "nonprofit", "公益", "公益项目", "社会创新"}:
        return "public_welfare"
    if value in {"commercial", "business", "商业", "商业项目"}:
        return "commercial"
    return "auto"


def _infer_project_type(plan_text: str, preferred: str = "auto") -> str:
    normalized = _normalize_project_type(preferred)
    if normalized != "auto":
        return normalized

    text = str(plan_text or "").lower()
    welfare_keywords = (
        "公益",
        "志愿",
        "社会价值",
        "弱势",
        "公共服务",
        "社会问题",
        "乡村",
        "教育公平",
        "医疗可及",
        "无障碍",
        "环保",
    )
    if any(kw in text for kw in welfare_keywords):
        return "public_welfare"
    return "commercial"


def _parse_json_block(content: str) -> Dict[str, Any] | None:
    raw = str(content or "").strip()
    if raw.startswith("```"):
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw, flags=re.IGNORECASE)
        if fenced:
            raw = fenced.group(1).strip()
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _history_window(history: List[Dict[str, Any]] | None, limit: int = 10) -> List[Dict[str, Any]]:
    rows = list(history or [])
    if not rows:
        return []
    return rows[-max(1, int(limit)):]


def _latest_working_draft(history: List[Dict[str, Any]] | None) -> str:
    for row in reversed(list(history or [])):
        if str(row.get("role") or "").strip().lower() not in {"ai", "assistant"}:
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        if "计划书工作稿" in content or "执行摘要" in content or "商业计划书" in content:
            return content[:2400]
    return ""


class CompetitionCoachAgent:
    def _project_type_rules(self, project_type: str) -> str:
        if project_type == "public_welfare":
            return (
                "项目类型=公益项目。重点是受益群体覆盖、社会影响评估、合规伦理、"
                "可持续运营与多元资金结构（政府/基金会/CSR/服务收入）。"
                "不得只以商业利润最大化作为唯一目标。"
            )
        return (
            "项目类型=商业项目。重点是用户价值、市场规模、增长路径、"
            "单位经济、盈利模型、现金流与可规模化能力。"
        )

    def _competition_hint(self, competition: str) -> str:
        name = str(competition or "").strip().lower()
        if "挑战杯" in name:
            return "挑战杯侧重创新性、社会价值与可验证成果。"
        if "大创" in name or "大学生创新创业训练" in name:
            return "大创侧重研究基础、实施方案、实验方法与阶段成果。"
        if "互联网+" in name or "互联网" in name:
            return "互联网+侧重商业化、产品化、用户增长与财务闭环。"
        if "公益" in name or "志愿" in name or "社会" in name:
            return "公益类赛事侧重社会影响、受益人覆盖、伦理与可持续机制。"
        return "请按主流双创赛事标准，给出可执行、可验证、可追踪的改进建议。"

    def chat(
        self,
        competition: str,
        plan_text: str,
        question: str,
        history: List[Dict[str, Any]] | None = None,
        hypergraph_context: Dict[str, Any] | None = None,
        project_type: str = "auto",
    ) -> Dict[str, Any]:
        graph = build_preview_graph(limit=80)
        node_count = len(graph.get("nodes") or [])
        edge_count = len(graph.get("links") or [])

        history_window = _history_window(history, limit=10)
        working_draft = _latest_working_draft(history_window)
        hg = hypergraph_context or {}
        normalized_type = _infer_project_type(plan_text, preferred=project_type)

        compact_hg = {
            "enabled": bool(hg.get("enabled")),
            "input_type": hg.get("input_type"),
            "matched_project": hg.get("matched_project")
            or {
                "id": hg.get("matched_project_node_id"),
                "name": hg.get("matched_project_name"),
            },
            "metrics": hg.get("metrics") or {},
            "consistency_alerts": (hg.get("consistency_alerts") or hg.get("warnings") or [])[:8],
            "missing_node_labels": (hg.get("missing_node_labels") or hg.get("missing_key_nodes") or [])[:8],
            "provenance": {
                "node_sources": (hg.get("provenance") or {}).get("node_sources", [])[:6],
                "hyperedge_evidence": (hg.get("provenance") or {}).get("hyperedge_evidence", [])[:6],
            },
            "similar_projects": (hg.get("similar_projects") or [])[:3],
            "risk_patterns": (hg.get("risk_patterns") or [])[:5],
            "suggested_evidence": (hg.get("suggested_evidence") or [])[:5],
        }

        prompt = (
            "你是竞赛教练，并同时扮演：市场分析专员、财务分析师、文案润色员。\n"
            "你的任务不是只点评，而是与学生协作推进计划书落地。\n"
            f"赛事类型：{competition}\n"
            f"赛事提示：{self._competition_hint(competition)}\n"
            f"项目类型：{normalized_type}\n"
            f"项目规则：{self._project_type_rules(normalized_type)}\n"
            f"项目文本：{(plan_text or '')[:4500]}\n"
            f"用户问题：{question}\n"
            f"历史对话：{json.dumps(history_window, ensure_ascii=False)[:1800]}\n"
            f"当前工作稿（如有）：{working_draft}\n"
            f"图谱规模：节点{node_count}，边{edge_count}\n"
            f"超图诊断摘要：{json.dumps(compact_hg, ensure_ascii=False)[:2000]}\n"
            "你必须在一次回复里同时完成“答疑 + 计划书迭代”：\n"
            "1) 先回答学生本轮问题；\n"
            "2) 再给出可直接复制的“计划书工作稿（迭代版）”。\n"
            "输出建议：使用 Markdown，结构可灵活组织；优先保证内容完整、可执行、可验证。\n"
            "请尽量覆盖：本轮结论、市场/财务/文案三类建议、计划书迭代稿、下一步单一任务。\n"
            "工作稿应在上一版基础上迭代，不要重写成空模板。"
        )

        system = (
            "你是高校创新创业竞赛总教练。"
            "请优先给出可落地建议，必要时指出证据缺口，并给出补证路径。"
        )

        llm = call_llm(prompt=prompt, system_prompt=system, temperature=0.25, timeout_seconds=60)
        if not llm:
            raise RuntimeError("生成竞赛建议失败，请稍后重试")

        return {
            "answer": llm,
            "project_type": normalized_type,
            "graph_stats": {"node_count": node_count, "edge_count": edge_count},
            "roles": ["市场分析专员", "财务分析师", "文案润色员"],
        }

    def co_write_plan(
        self,
        competition: str,
        plan_text: str,
        history: List[Dict[str, Any]] | None = None,
        project_type: str = "auto",
    ) -> Dict[str, Any]:
        normalized_type = _infer_project_type(plan_text, preferred=project_type)
        prompt = (
            "你是竞赛教练，请与学生协作生成可继续编辑的完整计划书草案。\n"
            "仅输出 JSON，不要输出 JSON 外文本。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "project_type": "commercial|public_welfare",\n'
            '  "title": "",\n'
            '  "sections": [{"name": "", "content": ""}],\n'
            '  "competition_adaptations": [{"competition": "", "revision": ""}],\n'
            '  "checklist": [""],\n'
            '  "next_actions": [""],\n'
            '  "markdown": "完整 Markdown 文本"\n'
            "}\n"
            f"赛事：{competition}\n"
            f"赛事提示：{self._competition_hint(competition)}\n"
            f"项目类型：{normalized_type}\n"
            f"项目规则：{self._project_type_rules(normalized_type)}\n"
            f"项目文本：{(plan_text or '')[:5200]}\n"
            f"历史对话：{json.dumps(history or [], ensure_ascii=False)[:1800]}"
        )

        system = (
            "你是双创竞赛总教练。"
            "输出内容必须结构化、可执行、可直接用于后续 Word 导出。"
        )

        content = call_llm(prompt=prompt, system_prompt=system, temperature=0.2, timeout_seconds=45)
        parsed = _parse_json_block(content or "")
        if parsed:
            parsed.setdefault("project_type", normalized_type)
            return parsed

        fallback_markdown = (
            f"# {competition}计划书草案\n\n"
            "## 一、项目概述\n请补充项目定位、核心价值与目标用户。\n\n"
            "## 二、问题与需求\n请补充痛点证据、使用场景与替代方案。\n\n"
            "## 三、解决方案\n请补充方案流程、关键功能、技术壁垒。\n\n"
            "## 四、实施与里程碑\n请补充3个月/6个月/12个月目标与资源配置。\n\n"
            "## 五、财务与可持续性\n"
            "商业项目补充 TAM/SAM/SOM、收入模型、成本结构；"
            "公益项目补充受益人规模、资金来源与影响评估机制。\n"
        )

        return {
            "project_type": normalized_type,
            "title": f"{competition}计划书草案",
            "sections": [
                {"name": "项目概述", "content": "请补充项目定位、核心价值与目标用户。"},
                {"name": "问题与需求", "content": "请补充痛点证据、应用场景与替代方案。"},
                {"name": "解决方案", "content": "请补充方案流程、关键功能与差异化优势。"},
                {"name": "实施与里程碑", "content": "请补充阶段目标、资源配置与风险预案。"},
                {
                    "name": "财务与可持续性",
                    "content": "请补充 TAM/SAM/SOM 或公益资金结构、成本与风险控制。",
                },
            ],
            "competition_adaptations": [
                {"competition": "挑战杯", "revision": "强化创新性、社会价值与可验证成果证据。"},
                {"competition": "大创", "revision": "强化研究基础、方法设计与实验验证路径。"},
                {"competition": "互联网+", "revision": "强化商业化路径、增长策略与单位经济数据。"},
                {"competition": "公益类赛事", "revision": "强化受益覆盖、社会影响评估与可持续运营机制。"},
            ],
            "checklist": ["关键假设是否可验证", "证据链是否可追溯", "里程碑是否可执行"],
            "next_actions": ["补齐核心证据链", "完善财务或资金模型", "完成赛事定向改写"],
            "markdown": fallback_markdown,
        }
