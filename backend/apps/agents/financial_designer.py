from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List

from ..core.services.llm_gateway import call_llm


PROJECT_TYPE_ALIASES = {
    "public_welfare": {"public_welfare", "public", "nonprofit", "公益", "公益项目", "非营利"},
    "commercial": {"commercial", "business", "商业", "商业项目"},
}

PROJECT_TYPE_KEYWORDS = {
    "public_welfare": ("公益", "志愿", "社会价值", "社会问题", "弱势", "公共服务", "非营利", "社区服务"),
}

FOCUS_RULES = {
    "budget": {
        "keywords": ("预算", "预算表", "拆分", "测算", "重算", "压缩", "投入"),
        "hint": "优先重排预算结构，区分一次性投入、固定成本、变动成本和预备金。",
    },
    "cash_flow": {
        "keywords": ("现金流", "跑道", "回款", "垫资", "消耗", "周转"),
        "hint": "重点说明回款节奏、支出峰值、预警线和现金储备。",
    },
    "revenue": {
        "keywords": ("收入", "盈利", "收费", "定价", "客单价", "复购", "毛利"),
        "hint": "优先校准收入结构、定价口径、复购逻辑和毛利空间。",
    },
    "cost": {
        "keywords": ("成本", "费用", "租金", "人工", "设备", "原料", "采购"),
        "hint": "重点拆解成本口径，找出可压缩项和必须投入项。",
    },
    "financing": {
        "keywords": ("融资", "资金", "投资", "现金储备", "贷款", "股权"),
        "hint": "说明资金来源、使用顺序、融资节奏和触发条件。",
    },
    "break_even": {
        "keywords": ("盈亏平衡", "回本", "回收期", "保本"),
        "hint": "补齐盈亏平衡公式、关键假设和触发阈值。",
    },
    "market": {
        "keywords": ("tam", "sam", "som", "市场", "规模", "渗透率"),
        "hint": "补充市场规模口径、分层方法和假设来源。",
    },
    "risk": {
        "keywords": ("风险", "波动", "不确定", "预警", "合规"),
        "hint": "补齐风险预警指标、替代方案和止损动作。",
    },
}

DOMAIN_PROFILES = {
    "public_welfare": {
        "trigger": ("公益", "志愿", "社区服务", "残障", "老人", "儿童", "乡村"),
        "revenue_streams": ["公益项目资金", "政府/基金会合作", "培训与咨询服务"],
        "cost_structure": ["项目执行成本", "运营与组织成本", "服务交付与评估成本"],
        "risk_controls": ["设置资金到账延迟预案", "按季度复核受益人覆盖与执行成本", "同步保留替代合作方名单"],
        "funding_sources": ["公益基金", "政府购买服务", "企业合作资金"],
    },
    "catering": {
        "trigger": ("咖啡", "奶茶", "饮品", "餐饮", "门店", "轻食", "堂食"),
        "revenue_streams": ["核心产品销售", "套餐/加购", "会员储值与复购"],
        "cost_structure": ["房租与水电", "人工成本", "设备折旧与原材料"],
        "risk_controls": ["设置日均销售预警线", "控制损耗率和库存周转天数", "区分淡旺季备货策略"],
        "funding_sources": ["自有资金", "校内/区域合作资金", "小额经营贷款或天使资金"],
    },
    "saas": {
        "trigger": ("saas", "软件", "平台", "系统", "小程序", "app", "应用"),
        "revenue_streams": ["订阅收入", "增值模块收入", "实施与服务收入"],
        "cost_structure": ["研发成本", "云资源与运维", "销售获客成本"],
        "risk_controls": ["监控客户流失率", "设定月度现金消耗上限", "按月复核 CAC/LTV"],
        "funding_sources": ["自有资金", "天使投资", "产业合作资金"],
    },
    "hardware": {
        "trigger": ("硬件", "设备", "机器人", "传感器", "制造"),
        "revenue_streams": ["设备销售", "售后服务", "耗材或配件收入"],
        "cost_structure": ["研发打样", "原材料与生产", "渠道与售后支持"],
        "risk_controls": ["设置备料上限", "锁定关键供应商", "按批次复盘毛利率"],
        "funding_sources": ["自有资金", "产业基金", "订单预付款或融资租赁"],
    },
    "education": {
        "trigger": ("教育", "课程", "培训", "校园", "学生", "教学"),
        "revenue_streams": ["课程服务收入", "机构合作收入", "增值辅导服务"],
        "cost_structure": ["内容研发", "师资与服务交付", "渠道运营"],
        "risk_controls": ["按月复核获客成本", "区分续费率与完课率", "保留课程迭代预算"],
        "funding_sources": ["自有资金", "校企合作资金", "政策扶持资金"],
    },
    "generic": {
        "trigger": (),
        "revenue_streams": ["核心产品或服务收入", "增值服务收入", "合作渠道收入"],
        "cost_structure": ["固定运营成本", "执行与交付成本", "市场与渠道成本"],
        "risk_controls": ["设置月度预算偏差预警", "保留应急现金储备", "按阶段复核关键假设"],
        "funding_sources": ["自有资金", "合作资金", "外部融资或专项资金"],
    },
}

DOMAIN_KEYWORDS = [
    "咖啡", "奶茶", "饮品", "餐饮", "门店", "轻食", "校园", "教育", "课程", "培训",
    "SaaS", "saas", "软件", "平台", "系统", "小程序", "APP", "app", "应用",
    "硬件", "设备", "机器人", "传感器", "制造", "农业", "医疗", "养老", "文旅",
    "公益", "志愿", "社区", "乡村", "电商", "直播", "物流", "供应链", "环保",
]

TOPIC_STOPWORDS = {
    "项目", "创业", "创新", "用户", "目标", "方案", "计划", "市场", "模式", "商业",
    "团队", "产品", "服务", "平台", "系统", "项目书", "计划书", "学生", "老师", "当前",
    "分析", "设计", "预算", "收入", "成本", "资金", "风险", "问题", "需要", "通过",
    "进行", "实现", "提升", "优化", "核心", "阶段", "结构", "逻辑", "验证", "数据",
}


def _normalize_project_type(project_type: str) -> str:
    value = str(project_type or "").strip().lower()
    for normalized, aliases in PROJECT_TYPE_ALIASES.items():
        if value in aliases:
            return normalized
    return "auto"


def _infer_project_type(plan_text: str, preferred: str = "auto") -> str:
    normalized = _normalize_project_type(preferred)
    if normalized != "auto":
        return normalized
    text = str(plan_text or "").lower()
    if any(keyword.lower() in text for keyword in PROJECT_TYPE_KEYWORDS["public_welfare"]):
        return "public_welfare"
    return "commercial"


def _history_to_text(history: Any, limit: int = 8) -> str:
    rows = history if isinstance(history, list) else []
    lines: List[str] = []
    for item in rows[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "student").strip().lower()
        content = str(item.get("content") or item.get("text") or "").strip()
        if not content:
            continue
        speaker = "学生" if role in {"student", "user"} else "财务智能体"
        lines.append(f"{speaker}: {content[:280]}")
    return "\n".join(lines)


def _compact_json(value: Any, limit: int = 2600) -> str:
    if value is None:
        return ""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value)
    return text[:limit]


def _compact_hypergraph_context(hypergraph_context: Dict[str, Any] | None) -> Dict[str, Any]:
    hg = hypergraph_context or {}
    provenance = hg.get("provenance") or {}
    return {
        "enabled": bool(hg.get("enabled")),
        "matched_project": hg.get("matched_project") or {
            "id": hg.get("matched_project_node_id"),
            "name": hg.get("matched_project_name"),
        },
        "metrics": hg.get("metrics") or {},
        "entity_match_stats": hg.get("entity_match_stats") or {},
        "consistency_alerts": (hg.get("consistency_alerts") or hg.get("warnings") or [])[:6],
        "missing_node_labels": (hg.get("missing_node_labels") or hg.get("missing_key_nodes") or [])[:6],
        "risk_patterns": (hg.get("risk_patterns") or [])[:4],
        "suggested_evidence": (hg.get("suggested_evidence") or [])[:5],
        "similar_projects": (hg.get("similar_projects") or [])[:3],
        "provenance": {
            "node_sources": (provenance.get("node_sources") or [])[:4],
            "hyperedge_evidence": (provenance.get("hyperedge_evidence") or [])[:4],
        },
        "diagnosis_summary": hg.get("diagnosis_summary") or {},
    }


def _render_hypergraph_prompt_block(hypergraph_context: Dict[str, Any] | None) -> str:
    compact = _compact_hypergraph_context(hypergraph_context)
    if not compact.get("enabled"):
        return ""
    matched = compact.get("matched_project") or {}
    diagnosis = compact.get("diagnosis_summary") or {}
    return (
        "\n以下是超图诊断结果，请把它作为财务判断的辅助证据，而不是忽略：\n"
        f"- 匹配项目: {matched.get('name') or matched.get('id') or '未匹配'}\n"
        f"- 关键缺失节点: {', '.join(str(x) for x in (compact.get('missing_node_labels') or [])[:4]) or '暂无'}\n"
        f"- 一致性提醒: {'；'.join(str(x) for x in (compact.get('consistency_alerts') or [])[:3]) or '暂无'}\n"
        f"- 风险模式: {'；'.join(str((row or {}).get('type') or row) for row in (compact.get('risk_patterns') or [])[:3]) or '暂无'}\n"
        f"- 建议补证: {'；'.join(str((row or {}).get('text') or row) for row in (compact.get('suggested_evidence') or [])[:3]) or '暂无'}\n"
        f"- 超图结论: {diagnosis.get('conclusion') or '暂无'}\n"
        f"- 结构化摘要(JSON): {_compact_json(compact, limit=1600)}\n"
    )


def _detect_domain_profile(plan_text: str, project_type: str) -> str:
    if project_type == "public_welfare":
        return "public_welfare"
    text = str(plan_text or "").lower()
    for name, profile in DOMAIN_PROFILES.items():
        if name in {"generic", "public_welfare"}:
            continue
        if any(keyword.lower() in text for keyword in profile["trigger"]):
            return name
    return "generic"


def _extract_topic_keywords(plan_text: str, limit: int = 6) -> list[str]:
    text = str(plan_text or "")
    found: list[str] = []
    for keyword in DOMAIN_KEYWORDS:
        if keyword.lower() in text.lower() and keyword not in found:
            found.append(keyword)
    fragments = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9\-\+]{2,}", text)
    counter = Counter()
    for token in fragments:
        clean = token.strip()
        if len(clean) < 2:
            continue
        if clean in TOPIC_STOPWORDS:
            continue
        if clean.lower() in {"project", "business", "commercial", "public", "welfare"}:
            continue
        counter[clean] += 1
    for token, _ in counter.most_common(limit * 2):
        if token not in found:
            found.append(token)
        if len(found) >= limit:
            break
    return found[:limit]


def _resolve_focuses(question: str) -> list[str]:
    raw = str(question or "").lower()
    focuses = [name for name, rule in FOCUS_RULES.items() if any(keyword.lower() in raw for keyword in rule["keywords"])]
    return focuses or ["budget", "cash_flow", "revenue"]


def _focus_keywords(focuses: list[str]) -> list[str]:
    keywords: list[str] = []
    for focus in focuses:
        rule = FOCUS_RULES.get(focus) or {}
        for keyword in rule.get("keywords") or ():
            if keyword not in keywords:
                keywords.append(keyword)
    return keywords


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, tuple):
        items = list(value)
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_action_list(value: Any) -> list[dict[str, str]]:
    rows = value if isinstance(value, list) else []
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        task = str(row.get("task") or "").strip()
        if not task:
            continue
        normalized.append(
            {
                "priority": str(row.get("priority") or "P2").strip() or "P2",
                "task": task,
                "owner": str(row.get("owner") or "项目负责人").strip() or "项目负责人",
                "deadline": str(row.get("deadline") or "两周内").strip() or "两周内",
            }
        )
    return normalized


def _merge_text_lists(primary: Any, secondary: Any, limit: int = 6) -> list[str]:
    merged: list[str] = []
    for source in (_normalize_text_list(primary), _normalize_text_list(secondary)):
        for item in source:
            if item not in merged:
                merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def _normalize_payload(data: Any, detected_type: str, current_plan: Any = None) -> Dict[str, Any]:
    base = data if isinstance(data, dict) else {}
    current = current_plan if isinstance(current_plan, dict) else {}

    tam = base.get("tam_sam_som") if isinstance(base.get("tam_sam_som"), dict) else {}
    current_tam = current.get("tam_sam_som") if isinstance(current.get("tam_sam_som"), dict) else {}

    profit = base.get("profit_model") if isinstance(base.get("profit_model"), dict) else {}
    current_profit = current.get("profit_model") if isinstance(current.get("profit_model"), dict) else {}

    funding = base.get("funding_strategy") if isinstance(base.get("funding_strategy"), dict) else {}
    current_funding = current.get("funding_strategy") if isinstance(current.get("funding_strategy"), dict) else {}

    plan = base.get("financial_plan") if isinstance(base.get("financial_plan"), dict) else {}
    current_plan_block = current.get("financial_plan") if isinstance(current.get("financial_plan"), dict) else {}

    return {
        "project_type": _normalize_project_type(base.get("project_type") or detected_type) if base.get("project_type") else detected_type,
        "tam_sam_som": {
            "tam": str(tam.get("tam") or current_tam.get("tam") or "").strip(),
            "sam": str(tam.get("sam") or current_tam.get("sam") or "").strip(),
            "som": str(tam.get("som") or current_tam.get("som") or "").strip(),
            "assumptions": _merge_text_lists(tam.get("assumptions"), current_tam.get("assumptions"), limit=6),
        },
        "profit_model": {
            "core_model": str(profit.get("core_model") or current_profit.get("core_model") or "").strip(),
            "revenue_streams": _merge_text_lists(profit.get("revenue_streams"), current_profit.get("revenue_streams"), limit=6),
            "cost_structure": _merge_text_lists(profit.get("cost_structure"), current_profit.get("cost_structure"), limit=6),
            "unit_economics": _merge_text_lists(profit.get("unit_economics"), current_profit.get("unit_economics"), limit=6),
        },
        "funding_strategy": {
            "sources": _merge_text_lists(funding.get("sources"), current_funding.get("sources"), limit=6),
            "stages": _merge_text_lists(funding.get("stages"), current_funding.get("stages"), limit=6),
        },
        "financial_plan": {
            "3_month": _merge_text_lists(plan.get("3_month"), current_plan_block.get("3_month"), limit=6),
            "12_month": _merge_text_lists(plan.get("12_month"), current_plan_block.get("12_month"), limit=6),
            "risk_controls": _merge_text_lists(plan.get("risk_controls"), current_plan_block.get("risk_controls"), limit=6),
        },
        "scorecard": [
            {
                "metric": str(item.get("metric") or "").strip(),
                "target": str(item.get("target") or "").strip(),
                "evidence": str(item.get("evidence") or "").strip(),
            }
            for item in (base.get("scorecard") or current.get("scorecard") or [])
            if isinstance(item, dict) and str(item.get("metric") or "").strip()
        ][:6],
        "action_list": _normalize_action_list(base.get("action_list") or current.get("action_list")),
        "summary": str(base.get("summary") or "").strip(),
        "assistant_reply": str(base.get("assistant_reply") or "").strip(),
    }


def _extract_json_object(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, flags=re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
    candidate = re.search(r"(\{[\s\S]*\})", text)
    return candidate.group(1).strip() if candidate else text


def _parse_json_payload(content: str) -> Dict[str, Any] | None:
    raw = _extract_json_object(content)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _build_topic_signature(topic_keywords: list[str]) -> str:
    return "、".join(topic_keywords[:4]) if topic_keywords else "当前项目"


def _payload_text(payload: Dict[str, Any]) -> str:
    parts = [
        str(payload.get("assistant_reply") or ""),
        str(payload.get("summary") or ""),
        _compact_json(payload.get("tam_sam_som")),
        _compact_json(payload.get("profit_model")),
        _compact_json(payload.get("funding_strategy")),
        _compact_json(payload.get("financial_plan")),
        _compact_json(payload.get("action_list")),
    ]
    return " ".join(part for part in parts if part).lower()


def _is_payload_grounded(
    payload: Dict[str, Any],
    plan_text: str,
    question: str,
    topic_keywords: list[str],
    focuses: list[str],
) -> bool:
    text = _payload_text(payload)
    if not text.strip():
        return False
    if question.strip():
        focus_keywords = _focus_keywords(focuses)
        if focus_keywords and not any(keyword.lower() in text for keyword in focus_keywords):
            return False
    if topic_keywords:
        topic_hits = [keyword for keyword in topic_keywords if len(keyword) >= 2 and keyword.lower() in text]
        if not topic_hits:
            return False
    if "saaS".lower() in text and "saas" not in plan_text.lower() and "软件" not in plan_text and "平台" not in plan_text:
        if any(keyword in plan_text for keyword in ("咖啡", "奶茶", "饮品", "门店", "餐饮")):
            return False
    return True


def _prompt_with_retry(previous_output: str) -> str:
    return (
        "上一次输出没有严格遵守要求，可能出现了非 JSON、跑题或与项目不一致的问题。"
        "请重新输出，只能输出一个 JSON 对象，不允许有任何解释文字。"
        f"\n上一次输出如下，请修正而不是重复：\n{previous_output[:2000]}"
    )


def _build_llm_prompt(
    plan_text: str,
    question: str,
    detected_type: str,
    competition: str,
    history_text: str,
    current_plan_text: str,
    hypergraph_block: str,
    topic_keywords: list[str],
    focuses: list[str],
) -> str:
    focus_hints = "；".join(FOCUS_RULES.get(focus, {}).get("hint", "") for focus in focuses if FOCUS_RULES.get(focus))
    return (
        "你是创新创业项目的财务预算智能体，需要围绕当前项目进行多轮预算讨论。"
        "本轮必须直接回应学生最新问题，并在上一轮预算基础上继续修改，而不是重新给一个无关模板。\n"
        "输出要求：只输出 JSON，不允许输出 JSON 之外的任何文字。\n"
        "JSON 结构如下：\n"
        "{\n"
        '  "project_type":"commercial|public_welfare",\n'
        '  "tam_sam_som":{"tam":"","sam":"","som":"","assumptions":[""]},\n'
        '  "profit_model":{"core_model":"","revenue_streams":[""],"cost_structure":[""],"unit_economics":[""]},\n'
        '  "funding_strategy":{"sources":[""],"stages":[""]},\n'
        '  "financial_plan":{"3_month":[""],"12_month":[""],"risk_controls":[""]},\n'
        '  "scorecard":[{"metric":"","target":"","evidence":""}],\n'
        '  "action_list":[{"priority":"P1|P2|P3","task":"","owner":"","deadline":""}],\n'
        '  "summary":"60-120字中文总结，说明本轮结论",\n'
        '  "assistant_reply":"120-260字中文回复，必须像对话一样直接回应学生这轮问题，并说明你改了什么、还缺什么"\n'
        "}\n"
        "硬性约束：\n"
        "1. 必须严格基于项目文本、历史对话、当前预算方案和本轮问题，不能脱离项目领域乱写。\n"
        "2. 如果项目文本没有提供具体数字，可以给出“建议口径/估算公式/假设项”，但要明确这是待验证假设，不能伪造事实。\n"
        "3. assistant_reply 必须直接回应学生这轮问题，例如“针对你这轮想调整的……，我先……”。\n"
        "4. 不要把餐饮项目写成 SaaS，不要把公益项目写成纯商业融资项目；若信息不足，只能补“待验证假设”。\n"
        "5. action_list 要可执行，避免空话。\n"
        f"项目类型: {detected_type}\n"
        f"竞赛场景: {competition or '未指定'}\n"
        f"项目主题关键词: {_build_topic_signature(topic_keywords)}\n"
        f"本轮关注点: {', '.join(focuses)}\n"
        f"本轮重点提示: {focus_hints or '围绕预算、收入、现金流展开'}\n"
        f"学生本轮问题: {question[:600] or '请基于已有方案继续迭代财务预算'}\n"
        f"历史对话:\n{history_text or '暂无'}\n"
        f"当前预算方案:\n{current_plan_text or '暂无'}\n"
        f"{hypergraph_block}"
        f"项目文本:\n{(plan_text or '')[:5200]}"
    )


def _default_revenue_streams(profile_name: str, project_type: str) -> list[str]:
    if project_type == "public_welfare":
        return DOMAIN_PROFILES["public_welfare"]["revenue_streams"]
    return DOMAIN_PROFILES.get(profile_name, DOMAIN_PROFILES["generic"])["revenue_streams"]


def _default_cost_structure(profile_name: str, project_type: str) -> list[str]:
    if project_type == "public_welfare":
        return DOMAIN_PROFILES["public_welfare"]["cost_structure"]
    return DOMAIN_PROFILES.get(profile_name, DOMAIN_PROFILES["generic"])["cost_structure"]


def _default_funding_sources(profile_name: str, project_type: str) -> list[str]:
    if project_type == "public_welfare":
        return DOMAIN_PROFILES["public_welfare"]["funding_sources"]
    return DOMAIN_PROFILES.get(profile_name, DOMAIN_PROFILES["generic"])["funding_sources"]


def _default_risk_controls(profile_name: str, project_type: str) -> list[str]:
    if project_type == "public_welfare":
        return DOMAIN_PROFILES["public_welfare"]["risk_controls"]
    return DOMAIN_PROFILES.get(profile_name, DOMAIN_PROFILES["generic"])["risk_controls"]


def _base_plan(
    plan_text: str,
    question: str,
    project_type: str,
    current_plan: Any,
    profile_name: str,
    topic_keywords: list[str],
) -> Dict[str, Any]:
    current = current_plan if isinstance(current_plan, dict) else {}
    topic = _build_topic_signature(topic_keywords)
    revenue_streams = _merge_text_lists(
        (current.get("profit_model") or {}).get("revenue_streams"),
        _default_revenue_streams(profile_name, project_type),
        limit=6,
    )
    cost_structure = _merge_text_lists(
        (current.get("profit_model") or {}).get("cost_structure"),
        _default_cost_structure(profile_name, project_type),
        limit=6,
    )
    funding_sources = _merge_text_lists(
        (current.get("funding_strategy") or {}).get("sources"),
        _default_funding_sources(profile_name, project_type),
        limit=6,
    )
    risk_controls = _merge_text_lists(
        (current.get("financial_plan") or {}).get("risk_controls"),
        _default_risk_controls(profile_name, project_type),
        limit=6,
    )
    core_model = str((current.get("profit_model") or {}).get("core_model") or "").strip()
    if not core_model:
        core_model = "社会价值实现 + 多元资金组合" if project_type == "public_welfare" else "核心价值交付 + 可复购收入"
    return {
        "project_type": project_type,
        "tam_sam_som": {
            "tam": str((current.get("tam_sam_som") or {}).get("tam") or f"先定义 {topic} 的总需求池，再标注测算口径").strip(),
            "sam": str((current.get("tam_sam_som") or {}).get("sam") or "缩小到首年可触达区域、渠道和客群").strip(),
            "som": str((current.get("tam_sam_som") or {}).get("som") or "按团队 12 个月可执行能力设定首年目标份额").strip(),
            "assumptions": _merge_text_lists(
                (current.get("tam_sam_som") or {}).get("assumptions"),
                [
                    "至少明确一个获客口径、一个转化口径和一个复购/留存口径",
                    "每个核心数字都要绑定数据来源或待验证假设",
                ],
                limit=6,
            ),
        },
        "profit_model": {
            "core_model": core_model,
            "revenue_streams": revenue_streams,
            "cost_structure": cost_structure,
            "unit_economics": _merge_text_lists(
                (current.get("profit_model") or {}).get("unit_economics"),
                [
                    "定义单个客户/单笔订单贡献毛利",
                    "拆出获客成本、履约成本和回本周期",
                    "区分试运营期与稳定期的单位经济变化",
                ],
                limit=6,
            ),
        },
        "funding_strategy": {
            "sources": funding_sources,
            "stages": _merge_text_lists(
                (current.get("funding_strategy") or {}).get("stages"),
                [
                    "0-3个月：验证关键财务假设，控制试错预算",
                    "4-8个月：放大有效渠道，复盘预算偏差",
                    "9-12个月：稳定现金流，准备下一阶段资金方案",
                ],
                limit=6,
            ),
        },
        "financial_plan": {
            "3_month": _merge_text_lists(
                (current.get("financial_plan") or {}).get("3_month"),
                [
                    "先做按月预算表，拆分固定成本、变动成本和一次性投入",
                    "为试运营设预算上限，并同步记录预算偏差",
                    "每周复核现金余额和回款节奏",
                ],
                limit=6,
            ),
            "12_month": _merge_text_lists(
                (current.get("financial_plan") or {}).get("12_month"),
                [
                    "按季度复盘预算偏差并调整资源配置",
                    "形成稳定的收入结构和现金流监控节奏",
                    "把高风险支出与可延后支出分层管理",
                ],
                limit=6,
            ),
            "risk_controls": risk_controls,
        },
        "scorecard": [
            {"metric": "预算偏差率", "target": "<=10%", "evidence": "月度预算与实际对比表"},
            {"metric": "现金储备覆盖月数", "target": ">=3个月", "evidence": "月度现金流台账"},
            {"metric": "单位经济验证", "target": "形成首轮测算", "evidence": "收入-成本-回本周期计算表"},
        ],
        "action_list": [
            {"priority": "P1", "task": "补齐本轮预算口径与关键假设表", "owner": "项目负责人", "deadline": "7天内"},
            {"priority": "P1", "task": "建立现金流台账并设置预警线", "owner": "财务负责人", "deadline": "7天内"},
            {"priority": "P2", "task": "用真实样本验证定价、成本或回款节奏", "owner": "运营负责人", "deadline": "14天内"},
        ],
        "summary": "",
        "assistant_reply": "",
        "raw_plan_excerpt": (plan_text or "")[:800],
        "latest_question": str(question or "").strip()[:200],
    }


def _adapt_plan_to_focuses(
    payload: Dict[str, Any],
    question: str,
    focuses: list[str],
    profile_name: str,
    project_type: str,
    topic_keywords: list[str],
    hypergraph_context: Dict[str, Any] | None,
) -> Dict[str, Any]:
    topic = _build_topic_signature(topic_keywords)
    financial_plan = payload["financial_plan"]
    profit_model = payload["profit_model"]
    funding = payload["funding_strategy"]
    tam = payload["tam_sam_som"]

    reply_lines = [f"针对你这轮想调整的“{str(question or '财务预算').strip()[:32]}”，我先沿用当前项目“{topic}”的口径继续细化。"]
    summary_points: list[str] = []

    if "budget" in focuses:
        financial_plan["3_month"] = _merge_text_lists(
            [
                "把预算拆成一次性投入、固定成本、变动成本三层，并给每层设置上限",
                "对一次性投入标注“必须立即投入/可延后投入/可替代投入”",
                "首月试运营预算建议单列，避免与常规运营预算混合",
            ],
            financial_plan.get("3_month"),
            limit=6,
        )
        payload["action_list"] = _normalize_action_list(
            [
                {"priority": "P1", "task": "重排预算表并标出可压缩项与不可压缩项", "owner": "财务负责人", "deadline": "3天内"},
                {"priority": "P2", "task": "为单月超支设置审批阈值和应急预案", "owner": "项目负责人", "deadline": "7天内"},
            ]
            + payload.get("action_list", [])
        )[:6]
        reply_lines.append("本轮重点放在预算拆分和优先级排序，先把一次性投入、固定成本、变动成本分开，才能判断哪些项能压、哪些项不能动。")
        summary_points.append("已把预算拆分逻辑前置，便于后续继续压缩或重算。")

    if "cash_flow" in focuses:
        financial_plan["risk_controls"] = _merge_text_lists(
            [
                "设置最低现金余额预警线，低于预警线时暂停非核心支出",
                "把回款周期和付款周期放进同一张月度现金流表",
                "保留至少 1-2 个月的缓冲资金或等价备用方案",
            ],
            financial_plan.get("risk_controls"),
            limit=6,
        )
        payload["scorecard"] = [
            {"metric": "月度净现金流", "target": "连续 3 个月可监控", "evidence": "月度现金流表"},
            {"metric": "现金预警线", "target": ">=1-2个月固定支出", "evidence": "现金余额日报/周报"},
        ] + [row for row in payload.get("scorecard", []) if row.get("metric") not in {"月度净现金流", "现金预警线"}]
        reply_lines.append("你如果主要担心现金流，就不要只看总预算，还要把回款时点、付款时点和最低现金余额一起看。")
        summary_points.append("补充了现金流预警和回款节奏控制。")

    if "revenue" in focuses:
        profit_model["unit_economics"] = _merge_text_lists(
            [
                "至少明确单笔收入、对应成本和单笔毛利",
                "对高毛利项和引流项分开测算，避免平均值掩盖问题",
                "把复购/续费假设单独列出来，不要直接写死",
            ],
            profit_model.get("unit_economics"),
            limit=6,
        )
        reply_lines.append("收入侧建议继续往下拆到“谁付钱、按什么付、多久复购一次”，这样预算和现金流才能真正对上。")
        summary_points.append("收入结构和单位经济口径已补强。")

    if "cost" in focuses:
        profit_model["cost_structure"] = _merge_text_lists(
            [
                "把必须投入项、试错投入项、可延后投入项分组",
                "把人工、场地/设备、材料/渠道分开统计",
            ],
            profit_model.get("cost_structure"),
            limit=6,
        )
        reply_lines.append("成本侧我建议用“必须投入/可延后/可替代”三分法，不然每次压预算都会互相打架。")
        summary_points.append("成本口径已改成可压缩与不可压缩分层。")

    if "financing" in focuses:
        funding["stages"] = _merge_text_lists(
            [
                "先明确现有自有资金能覆盖几个月，再判断是否需要外部资金",
                "若走融资或合作资金，要写清使用场景和触发条件",
                "不要把尚未落实的资金直接当成既有现金流",
            ],
            funding.get("stages"),
            limit=6,
        )
        reply_lines.append("如果这轮讨论的是融资或资金来源，关键不是渠道越多越好，而是先明确每一类资金什么时候进、解决什么缺口。")
        summary_points.append("资金来源和使用顺序已改为阶段化。")

    if "break_even" in focuses:
        payload["scorecard"] = [
            {"metric": "盈亏平衡点", "target": "形成可追踪公式", "evidence": "固定成本、毛利率、销量/客户量测算表"},
            {"metric": "回本周期", "target": "形成保守/基准/激进三档口径", "evidence": "预算情景对比表"},
        ] + [row for row in payload.get("scorecard", []) if row.get("metric") not in {"盈亏平衡点", "回本周期"}]
        reply_lines.append("如果要看回本或盈亏平衡，必须把固定成本、单笔毛利和销量/客户量阈值同时列出来。")
        summary_points.append("新增盈亏平衡与回本口径。")

    if "market" in focuses:
        tam["assumptions"] = _merge_text_lists(
            [
                "TAM 用总需求池口径，SAM 用首阶段可触达口径，SOM 用首年可实现口径",
                "每一层都要对应渠道、区域或客群范围，不要只写一个总数",
            ],
            tam.get("assumptions"),
            limit=6,
        )
        reply_lines.append("市场规模这块建议按 TAM/SAM/SOM 三层拆，不要把潜在全量需求直接当成首年收入基础。")
        summary_points.append("市场规模和预算口径的连接关系已补充。")

    if "risk" in focuses:
        financial_plan["risk_controls"] = _merge_text_lists(
            [
                "为销量不达标、成本上浮、回款延迟分别准备替代动作",
                "每月复核一次关键假设，连续两次偏离就触发调整",
            ],
            financial_plan.get("risk_controls"),
            limit=6,
        )
        reply_lines.append("风险控制这轮我补成了可触发的动作，不只是“注意风险”，而是明确偏差出现后怎么收缩预算和现金支出。")
        summary_points.append("风险预警和止损动作已具体化。")

    hypergraph = _compact_hypergraph_context(hypergraph_context)
    missing_nodes = hypergraph.get("missing_node_labels") or []
    if missing_nodes:
        reply_lines.append(f"另外，超图诊断里还提示你缺少“{'、'.join(str(x) for x in missing_nodes[:3])}”这类节点，预算里最好同步补上对应证据或假设来源。")
        summary_points.append("结合超图缺失节点补了预算证据要求。")

    payload["summary"] = "；".join(summary_points[:4]) or "已根据本轮问题调整预算结构、现金流和执行动作。"
    payload["assistant_reply"] = "".join(reply_lines)[:260]
    return payload


def _fallback_reply(
    plan_text: str,
    question: str,
    project_type: str,
    current_plan: Any,
    hypergraph_context: Dict[str, Any] | None,
) -> Dict[str, Any]:
    profile_name = _detect_domain_profile(plan_text, project_type)
    topic_keywords = _extract_topic_keywords(plan_text)
    focuses = _resolve_focuses(question)
    payload = _base_plan(
        plan_text=plan_text,
        question=question,
        project_type=project_type,
        current_plan=current_plan,
        profile_name=profile_name,
        topic_keywords=topic_keywords,
    )
    return _adapt_plan_to_focuses(
        payload=payload,
        question=question,
        focuses=focuses,
        profile_name=profile_name,
        project_type=project_type,
        topic_keywords=topic_keywords,
        hypergraph_context=hypergraph_context,
    )


class FinancialDesignAgent:
    def generate(
        self,
        plan_text: str,
        question: str = "",
        project_type: str = "auto",
        competition: str = "",
        history: Any = None,
        current_plan: Any = None,
        hypergraph_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        detected_type = _infer_project_type(plan_text, preferred=project_type)
        history_text = _history_to_text(history)
        current_plan_text = _compact_json(current_plan, limit=2600)
        topic_keywords = _extract_topic_keywords(plan_text)
        focuses = _resolve_focuses(question)
        hypergraph_block = _render_hypergraph_prompt_block(hypergraph_context)
        prompt = _build_llm_prompt(
            plan_text=plan_text,
            question=question,
            detected_type=detected_type,
            competition=competition,
            history_text=history_text,
            current_plan_text=current_plan_text,
            hypergraph_block=hypergraph_block,
            topic_keywords=topic_keywords,
            focuses=focuses,
        )
        system = (
            "你是严谨的创新创业财务预算智能体。"
            "你的职责是围绕当前项目和当前提问做连续预算迭代。"
            "你必须严格输出 JSON，不能输出解释。"
            "若信息不足，只能输出待验证假设和测算口径，不能编造项目行业或商业模式。"
        )

        llm_output = call_llm(prompt=prompt, system_prompt=system, temperature=0.2, timeout_seconds=60)
        if llm_output:
            parsed = _parse_json_payload(llm_output)
            normalized = _normalize_payload(parsed, detected_type, current_plan=current_plan) if parsed else None
            if normalized and _is_payload_grounded(normalized, plan_text, question, topic_keywords, focuses):
                if not normalized.get("assistant_reply"):
                    normalized["assistant_reply"] = normalized.get("summary") or "已根据本轮问题更新财务预算。"
                if not normalized.get("summary"):
                    normalized["summary"] = "已根据当前项目和本轮问题完成财务预算调整。"
                normalized["raw_plan_excerpt"] = (plan_text or "")[:800]
                normalized["latest_question"] = str(question or "").strip()[:200]
                return normalized

            repair_prompt = prompt + "\n\n" + _prompt_with_retry(llm_output)
            repaired_output = call_llm(prompt=repair_prompt, system_prompt=system, temperature=0.1, timeout_seconds=45)
            repaired = _parse_json_payload(repaired_output or "")
            normalized = _normalize_payload(repaired, detected_type, current_plan=current_plan) if repaired else None
            if normalized and _is_payload_grounded(normalized, plan_text, question, topic_keywords, focuses):
                if not normalized.get("assistant_reply"):
                    normalized["assistant_reply"] = normalized.get("summary") or "已根据本轮问题更新财务预算。"
                if not normalized.get("summary"):
                    normalized["summary"] = "已根据当前项目和本轮问题完成财务预算调整。"
                normalized["raw_plan_excerpt"] = (plan_text or "")[:800]
                normalized["latest_question"] = str(question or "").strip()[:200]
                return normalized

        return _fallback_reply(
            plan_text=plan_text,
            question=question,
            project_type=detected_type,
            current_plan=current_plan,
            hypergraph_context=hypergraph_context,
        )
