from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Any

from .models import CaseLibraryDocument, PromptSceneConfig, ScoringRubric
from .prompts import GUIDE_SYSTEM_PROMPT, PDF_REVIEW_PROMPT, TEACHER_REVIEW_PROMPT, build_scene_prompt
from .services.llm_gateway import call_llm


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except Exception:
        return default


LLM_REVIEW_TIMEOUT_SECONDS = max(30, min(600, _read_int_env("LLM_REVIEW_TIMEOUT_SECONDS", 120)))

STUDENT_SYSTEM_PROMPT = GUIDE_SYSTEM_PROMPT
TEACHER_SYSTEM_PROMPT = TEACHER_REVIEW_PROMPT
PDF_REVIEW_SYSTEM_PROMPT = PDF_REVIEW_PROMPT

PROMPT_POLICY = {
    "student": "以指导老师身份讲解和举例，可提供方法建议，但不能直接代写完整项目。",
    "teacher": "输出问题清单与可执行修改建议，供教师二次编辑。",
}

PROJECT_RELATED_KEYWORDS = {
    "创新", "创业", "项目", "计划书", "商业", "公益", "用户", "痛点", "需求", "场景", "方案", "产品", "服务",
    "市场", "竞品", "验证", "访谈", "问卷", "试点", "数据", "商业模式", "盈利", "收入", "成本", "现金流", "风险",
    "里程碑", "执行", "团队", "融资", "路演", "mvp", "可行性", "评审", "竞赛",
}

COMPLETENESS_SECTIONS = {
    "problem": {
        "label": "问题定义",
        "keywords": ["痛点", "问题", "需求", "场景", "现状", "背景"],
        "question": "如果评委追问“你到底在解决什么具体问题”，你会如何用一句话说清楚？",
    },
    "user": {
        "label": "目标用户",
        "keywords": ["用户", "客户", "画像", "人群", "对象", "受众"],
        "question": "如果评委追问“这个项目主要服务谁”，你能否给出清晰的主用户和使用场景？",
    },
    "solution": {
        "label": "解决方案",
        "keywords": ["方案", "产品", "服务", "功能", "系统", "平台"],
        "question": "如果评委继续追问“你的方案具体怎么解决前面的问题”，你能否拿出清晰的解决链路？",
    },
    "validation": {
        "label": "验证证据",
        "keywords": ["验证", "访谈", "问卷", "试点", "实验", "数据", "样本", "反馈"],
        "question": "如果评委要求你证明判断不是主观猜测，你现在能提供哪些数据、访谈或试点证据？",
    },
    "business": {
        "label": "商业模式",
        "keywords": ["商业模式", "盈利", "收入", "付费", "成本", "渠道", "获客", "运营"],
        "question": "如果评委追问“这个项目如何形成收益或稳定运营”，你能否说清收入来源与成本结构？",
    },
    "plan": {
        "label": "实施计划",
        "keywords": ["计划", "里程碑", "排期", "时间表", "团队", "分工", "资源", "风险"],
        "question": "如果评委追问“项目下一步怎么落地”，你能否说清时间、分工、资源和风险应对？",
    },
}

SECTION_PATTERNS = {
    "problem": [
        re.compile(r"(痛点|问题|需求|难题|矛盾)"),
        re.compile(r"(解决|缓解|应对).{0,20}(问题|痛点|需求|难题)"),
    ],
    "user": [
        re.compile(r"(用户|客户|画像|受众|人群|对象)"),
        re.compile(r"(面向|针对|服务|聚焦).{0,24}(学生|教师|家长|老人|儿童|企业|商户|患者|居民|学校|机构|群体|消费者|创业者)"),
    ],
    "solution": [
        re.compile(r"(方案|产品|服务|功能|系统|平台)"),
        re.compile(r"(开发|设计|构建|推出|提供).{0,24}(平台|系统|服务|产品|工具|设备|方案)"),
    ],
    "validation": [
        re.compile(r"(验证|访谈|问卷|试点|实验|反馈|样本|数据)"),
        re.compile(r"\d+.{0,12}(访谈|问卷|样本|试点|反馈|用户)"),
    ],
    "business": [
        re.compile(r"(商业模式|盈利|收入|付费|成本|渠道|获客|运营)"),
        re.compile(r"(广告|订阅|服务费|会员费|佣金|毛利|现金流)"),
    ],
    "plan": [
        re.compile(r"(计划|里程碑|排期|时间表|团队|分工|资源|风险)"),
        re.compile(r"(mvp|试点|上线|阶段目标|三个月|6个月|12个月|负责人)"),
    ],
}

RISK_COLOR_MAP = {
    "low": "#1e88e5",
    "medium": "#fbc02d",
    "high": "#ef6c00",
}

OFF_TOPIC_HINT = (
    "当前内容与创新创业项目计划书的关联度很低，暂时无法按项目检阅。"
    "如果你要提交项目书，请至少先说明项目主题、目标用户、核心痛点、解决方案和验证思路。"
)

STAGE_FLOW = {
    "idea": "user",
    "user": "pain",
    "pain": "solution",
    "solution": "validation",
    "validation": "business",
    "business": "plan",
    "plan": "plan",
}

STAGE_QUESTIONS = {
    "idea": "你现在最想解决的现实问题是什么？这个问题具体发生在什么场景里？",
    "user": "这个问题最典型的目标用户是谁？请说出至少一个具体用户群体。",
    "pain": "这个用户现在最难受的痛点是什么？为什么这个问题值得被优先解决？",
    "solution": "你的方案如何解决这个痛点？与现有替代方案相比，关键差异是什么？",
    "validation": "你已经或准备通过哪些访谈、问卷、试点或数据来验证这个方案？",
    "business": "项目如何形成可持续运营？收入来源、关键成本和获客方式分别是什么？",
    "plan": "接下来3个月你准备先做什么？谁来做？用什么指标判断推进效果？",
}

KNOWLEDGE_HINTS = {
    "idea": "先把问题说具体，不要一开始就写宏大愿景。",
    "user": "用户画像至少应包含角色、场景、约束和决策特征。",
    "pain": "痛点最好能被验证，尽量配访谈原话、数据或案例。",
    "solution": "方案要能对上前面的用户与问题，不要只罗列功能名词。",
    "validation": "关键判断至少要有一条证据：访谈、数据、实验或试点反馈。",
    "business": "商业模式要同时说清收入、成本、客户和渠道。",
    "plan": "实施计划要落到时间、里程碑、负责人和风险预案。",
}

RUBRIC_DEFAULTS = [
    {"code": "innovation", "label": "创新点", "weight": 20, "prompt_hint": "是否明确写出创新点、独特性和与痛点的对应关系"},
    {"code": "logic", "label": "逻辑框架", "weight": 20, "prompt_hint": "痛点、方案、盈利模式、实施计划之间是否形成闭环"},
    {"code": "feasibility", "label": "可行性", "weight": 20, "prompt_hint": "是否考虑成本、资源、落地难度和风险约束"},
    {"code": "completeness", "label": "完整性", "weight": 20, "prompt_hint": "是否缺失关键环节，如盈利模式、验证或风险应对"},
    {"code": "competition", "label": "大赛适配", "weight": 20, "prompt_hint": "是否覆盖评委常见关注点，如市场、竞品、证据和亮点"},
]

RUBRIC_9_DIMENSIONS = [
    "Problem Definition",
    "User Evidence Strength",
    "Solution Feasibility",
    "Business Model Consistency",
    "Market & Competition",
    "Financial Logic",
    "Innovation & Differentiation",
    "Team & Execution",
    "Presentation & Material Quality",
]

COMMON_ISSUE_RULES = [
    ("用户研究不足", ["用户", "访谈", "问卷", "样本", "调研", "画像"]),
    ("问题定义不清", ["痛点", "问题", "场景", "需求", "背景"]),
    ("方案论证不足", ["方案", "功能", "产品", "服务", "差异化"]),
    ("验证证据不足", ["验证", "数据", "试点", "实验", "证据", "反馈"]),
    ("商业模式不完整", ["商业模式", "盈利", "收入", "成本", "渠道", "获客"]),
    ("财务逻辑不足", ["财务", "现金流", "毛利", "利润", "预算", "回本"]),
    ("实施计划不清", ["计划", "里程碑", "分工", "时间表", "风险", "资源"]),
    ("市场竞品分析不足", ["市场", "竞品", "竞争", "行业", "tam", "sam", "som"]),
    ("表达与结构需要优化", ["标题", "摘要", "目录", "图表", "格式", "表达", "重复"]),
]

SCENE_PROMPT_DEFAULTS = {
    "student_pdf_review": {
        "fixed": "你正在回答学生关于项目计划书检阅结果的追问，要先解释判断依据，再给出引导性问题。",
        "variants": {
            "default": "优先说明为什么会被批注、证据缺口在哪里、学生下一步该思考什么。",
        },
    },
    "teacher_prep": {
        "fixed": "你正在帮助教师围绕学生项目做点评与课堂追问。",
        "variants": {
            "summary": "输出共性问题、讲解逻辑和可直接追问的话术。",
            "single_student": "围绕当前学生项目给出结论、证据和点评建议。",
            "teach_topic": "输出适合直接上课的讲解结构和追问路径。",
        },
    },
    "teacher_scoring": {
        "fixed": "你正在帮助教师对单个项目进行点评和评分解释。",
        "variants": {
            "default": "先说明判断依据，再给教师可直接复述的点评话术。",
        },
    },
}

NUMERIC_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def _normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _truncate(text: Any, limit: int) -> str:
    value = _normalize_text(text)
    return value if len(value) <= limit else f"{value[: max(limit - 1, 0)]}…"


def _has_number(text: str) -> bool:
    return bool(NUMERIC_PATTERN.search(str(text or "")))


def _contains_any(text: str, keywords: list[str] | set[str] | tuple[str, ...]) -> bool:
    base = str(text or "").lower()
    return any(str(keyword).lower() in base for keyword in keywords if str(keyword).strip())


def _count_hits(text: str, keywords: list[str] | set[str] | tuple[str, ...]) -> int:
    base = str(text or "").lower()
    return sum(1 for keyword in keywords if str(keyword).strip() and str(keyword).lower() in base)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return default
    try:
        return int(float(text))
    except Exception:
        return default


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        preferred = ["text", "summary", "detail", "reason", "message", "conclusion", "name", "label", "type", "source"]
        parts = [_normalize_text(value.get(key)) for key in preferred if _normalize_text(value.get(key))]
        if parts:
            return "；".join(parts[:3])
        return _normalize_text(json.dumps(value, ensure_ascii=False))
    if isinstance(value, (list, tuple, set)):
        parts = [_stringify_value(item) for item in value]
        return "；".join([part for part in parts if part][:3])
    return _normalize_text(str(value))


def _call_llm(prompt: str, timeout_seconds: int = 180, system_prompt: str | None = None) -> str | None:
    return call_llm(
        prompt=prompt,
        system_prompt=system_prompt or STUDENT_SYSTEM_PROMPT,
        temperature=0.35,
        timeout_seconds=timeout_seconds,
    )


def _load_rubrics() -> list[dict[str, Any]]:
    try:
        rows = list(ScoringRubric.objects.filter(is_active=True).values("code", "label", "weight", "prompt_hint"))
        return rows or RUBRIC_DEFAULTS
    except Exception:
        return RUBRIC_DEFAULTS


def _load_case_patterns(limit: int = 2, industry: str = "", score_tag: str = "") -> list[dict[str, str]]:
    try:
        queryset = CaseLibraryDocument.objects.filter(clean_status=CaseLibraryDocument.CLEAN_DONE, privacy_masked=True)
        if industry:
            queryset = queryset.filter(industry_category__icontains=industry)
        rows = list(queryset.order_by("is_synthetic", "-updated_at")[: max(limit * 4, 4)])
    except Exception:
        return []

    if score_tag:
        filtered = []
        target = _normalize_text(score_tag)
        for row in rows:
            tags = [_normalize_text(item) for item in _safe_list(row.score_tags)]
            if target in tags:
                filtered.append(row)
        rows = filtered or rows

    rows = rows[: max(limit, 1)]
    payload: list[dict[str, str]] = []
    for row in rows:
        facts = row.core_facts or {}
        payload.append(
            {
                "industry": row.industry_category or "通用",
                "innovation": "；".join(_safe_list(facts.get("innovation"))[:2]) or "强调创新点与现有替代方案差异",
                "logic": "；".join(_safe_list(facts.get("logic"))[:2]) or "形成问题-方案-验证-模式-计划闭环",
                "feasibility": "；".join(_safe_list(facts.get("feasibility"))[:2]) or "说明资源、成本和风险应对",
            }
        )
    return payload


def _render_case_patterns(case_patterns: list[dict[str, str]]) -> str:
    if not case_patterns:
        return "暂无可用案例范式，按通用创新创业评审标准作答。"
    lines = []
    for idx, item in enumerate(case_patterns, start=1):
        lines.append(
            f"{idx}. 行业={item.get('industry', '通用')} | 创新={item.get('innovation', '')} | 逻辑={item.get('logic', '')} | 可行性={item.get('feasibility', '')}"
        )
    return "\n".join(lines)


def _load_scene_prompt(scene_key: str, variant: str, case_patterns: list[dict[str, str]]) -> str:
    try:
        config = PromptSceneConfig.objects.filter(scene_key=scene_key, is_active=True).first()
    except Exception:
        config = None
    if config:
        addon = (config.scene_prompts or {}).get(variant) or (config.scene_prompts or {}).get("default", "")
        return f"{_normalize_text(config.fixed_prompt)}\n补充规则：{_normalize_text(addon) or '无'}\n案例范式：\n{_render_case_patterns(case_patterns)}"
    return build_scene_prompt(scene_key, variant, case_patterns)


def _section_present(section_key: str, text: str) -> bool:
    content = str(text or "")
    config = COMPLETENESS_SECTIONS.get(section_key) or {}
    if _contains_any(content, config.get("keywords") or []):
        return True
    for pattern in SECTION_PATTERNS.get(section_key) or []:
        if pattern.search(content):
            return True
    return False


def _is_related_to_project(text: str) -> bool:
    content = _normalize_text(text).lower()
    if not content:
        return True
    keyword_hits = _count_hits(content, PROJECT_RELATED_KEYWORDS)
    structure_hits = sum(1 for key in COMPLETENESS_SECTIONS if _section_present(key, content))
    if keyword_hits >= 2 or structure_hits >= 2:
        return True
    idea_signal = _contains_any(
        content,
        ["我想做", "想做", "做一个", "做个平台", "做一款", "项目", "产品", "平台", "服务", "方案"],
    )
    problem_signal = _contains_any(
        content,
        ["解决", "缓解", "帮助", "改善", "提升", "降低", "痛点", "问题", "需求", "场景"],
    )
    return bool(idea_signal and (problem_signal or keyword_hits >= 1))


def _is_project_document(text: str) -> bool:
    content = _normalize_text(text)
    if len(content) < 40:
        return False
    if not _is_related_to_project(content):
        return False
    return sum(1 for key in COMPLETENESS_SECTIONS if _section_present(key, content)) >= 2


def _project_material_state(text: str) -> dict[str, Any]:
    content = _normalize_text(text)
    if not content:
        return {
            "related": False,
            "is_document": False,
            "is_partial_project": False,
            "keyword_hits": 0,
            "structure_hits": 0,
            "state": "unrelated",
        }

    keyword_hits = _count_hits(content, PROJECT_RELATED_KEYWORDS)
    structure_hits = sum(1 for key in COMPLETENESS_SECTIONS if _section_present(key, content))
    title_or_scene_hits = _count_hits(
        content,
        [
            "项目名称",
            "项目简介",
            "商业计划书",
            "创业计划书",
            "创新创业",
            "路演",
            "bp",
            "商业模式",
            "目标用户",
            "解决方案",
        ],
    )
    related = keyword_hits >= 2 or structure_hits >= 1 or (title_or_scene_hits >= 1 and len(content) >= 20)
    is_document = related and (
        (len(content) >= 180 and structure_hits >= 2)
        or (len(content) >= 100 and structure_hits >= 4)
    )
    return {
        "related": related,
        "is_document": is_document,
        "is_partial_project": related and not is_document,
        "keyword_hits": keyword_hits,
        "structure_hits": structure_hits,
        "state": "document" if is_document else ("partial_project" if related else "unrelated"),
    }


def _infer_risk_level(description: str) -> str:
    text = str(description or "")
    if _contains_any(text, ["缺少", "缺失", "高风险", "矛盾", "无法证明", "不完整", "断裂", "空缺"]):
        return "high"
    if _contains_any(text, ["建议", "补充", "完善", "细化", "量化", "说明", "不足"]):
        return "medium"
    return "low"


def _normalize_project_type(project_type: str, text: str = "") -> str:
    value = str(project_type or "").strip().lower()
    if value in {"public_welfare", "public", "nonprofit", "公益", "公益项目"}:
        return "public_welfare"
    if value in {"commercial", "business", "商业", "商业项目"}:
        return "commercial"
    return "public_welfare" if _contains_any(text, ["公益", "志愿", "社会价值", "社会问题", "公共服务", "弱势", "非营利"]) else "commercial"


def _detect_completeness(text: str) -> dict[str, Any]:
    raw = _normalize_text(text)
    if not raw:
        return {
            "is_complete": False,
            "progress": 0,
            "missing_parts": [{"key": "document", "part": "项目内容", "urgency": "high", "reason": "文档内容为空"}],
        }

    hit = 0
    missing = []
    for name, config in COMPLETENESS_SECTIONS.items():
        matched = _section_present(name, raw)
        if matched:
            hit += 1
            continue
        label = config.get("label") or name
        urgency = "high" if name in {"problem", "solution", "business"} else "medium"
        missing.append({"key": name, "part": label, "urgency": urgency, "reason": f"缺少{label}相关论证"})

    progress = int(round((hit / max(len(COMPLETENESS_SECTIONS), 1)) * 100))
    return {
        "is_complete": progress >= 75,
        "progress": progress,
        "missing_parts": missing,
    }


def _llm_incomplete_feedback(
    text: str,
    progress: int,
    missing_parts: list[dict[str, Any]],
    audience_role: str = "student",
) -> str:
    missing_text = "\n".join(
        [
            f"- {item.get('part', '未命名部分')} | 紧急程度: {item.get('urgency', 'medium')} | 原因: {item.get('reason', '')}"
            for item in missing_parts
        ]
    ) or "- 当前未识别到明确缺失项，请补充核心章节。"
    prompt = (
        "请你对当前提交的创新创业项目内容进行完整性检测。\n"
        "禁止行为：不得做细节批注，不得给 Rubric 评分/分数/等级，不得展示检阅触发规则。\n"
        "输出不要求固定模板，但内容至少覆盖：\n"
        "1) 项目当前整体进度说明；\n"
        "2) 缺失内容清单与紧急程度（低/中/高）；\n"
        "3) 下一步完善建议（优先高紧急项）。\n"
        "表达要求：简洁、专业、可执行，可用段落或小标题组织。\n"
        f"当前估计进度: {progress}%\n"
        f"缺失项检测结果:\n{missing_text}\n"
        f"项目文本:\n{(text or '')[:3000]}"
    )
    system_prompt = TEACHER_REVIEW_PROMPT if audience_role == "teacher" else PDF_REVIEW_PROMPT
    content = _call_llm(prompt, timeout_seconds=120, system_prompt=system_prompt)
    if content and content.strip():
        return content.strip()
    return (
        f"（1）项目当前整体进度说明\n当前项目完成度约为{progress}%，已具备部分基础内容，但关键模块尚未补齐。\n\n"
        "（2）缺失内容清单 + 紧急程度标注\n"
        + "\n".join([f"- {item.get('part', '未命名部分')}（{item.get('urgency', 'medium')}）: {item.get('reason', '')}" for item in missing_parts])
        + "\n\n（3）下一步完善建议\n建议优先补齐高紧急度模块，再完善中低紧急度内容，并补充可验证证据。"
    )


def _find_span(page_text: str, issue: dict[str, Any], index: int) -> tuple[int, int, str]:
    text = str(page_text or "")
    anchors = [
        str(issue.get("anchor") or "").strip(),
        str(issue.get("snippet") or "").strip(),
        str(issue.get("description") or "").strip(),
    ]
    for anchor in anchors:
        if anchor and anchor in text:
            start = text.index(anchor)
            end = start + len(anchor)
            snippet = text[max(0, start - 36): min(len(text), end + 88)].strip()
            return start, end, snippet
    if not text:
        return 0, 0, ""
    window = min(160, max(40, len(text) // 6 or 40))
    start = min(max(0, index * 96), max(len(text) - window, 0))
    end = min(len(text), start + window)
    return start, end, text[start:end].strip()


def _resolve_precise_span(page_text: str, issue: dict[str, Any]) -> tuple[int, int, str] | None:
    text = str(page_text or "")
    if not text:
        return None

    try:
        start = int(issue.get("start", -1))
        end = int(issue.get("end", -1))
    except Exception:
        return None

    if start < 0 or end <= start:
        return None

    text_length = len(text)
    if text_length <= 0:
        return None
    if start >= text_length or end <= 0:
        return None

    safe_start = max(0, min(start, text_length - 1))
    safe_end = max(safe_start + 1, min(end, text_length))
    exact_snippet = text[safe_start:safe_end].strip()
    if exact_snippet:
        return safe_start, safe_end, exact_snippet

    context_start = max(0, safe_start - 24)
    context_end = min(text_length, safe_end + 48)
    context_snippet = text[context_start:context_end].strip()
    if context_snippet:
        return safe_start, safe_end, context_snippet
    return None


def _estimate_paragraph_index(page_text: str, start: int) -> int:
    text = str(page_text or "")
    if not text:
        return 1
    prefix = text[: max(start, 0)]
    chunks = [chunk for chunk in re.split(r"\n{2,}|\r\n{2,}", prefix) if chunk.strip()]
    if chunks:
        return len(chunks) + 1
    lines = [line for line in prefix.splitlines() if line.strip()]
    return max(1, len(lines))


def _compact_hypergraph_context(hypergraph_context: dict[str, Any] | None) -> dict[str, Any]:
    hg = hypergraph_context or {}
    provenance = hg.get("provenance") or {}
    diagnosis_summary = hg.get("diagnosis_summary") or {}
    entity_stats = hg.get("entity_match_stats") or {}
    metrics = hg.get("metrics") or {}
    matched_project = hg.get("matched_project") or {
        "id": hg.get("matched_project_node_id"),
        "name": hg.get("matched_project_name"),
    }
    return {
        "enabled": bool(hg.get("enabled")),
        "input_type": hg.get("input_type") or "unknown",
        "matched_project": matched_project,
        "metrics": {
            "label_coverage_rate": metrics.get("label_coverage_rate"),
            "explainability_item_rate": metrics.get("explainability_item_rate"),
            "project_confidence_rate": metrics.get("project_confidence_rate"),
        },
        "entity_match_stats": {
            "matched_labels": _safe_list(entity_stats.get("matched_labels"))[:8],
            "matched_nodes": _safe_list(entity_stats.get("matched_nodes"))[:6],
        },
        "consistency_alerts": _safe_list(hg.get("consistency_alerts") or hg.get("warnings"))[:6],
        "missing_node_labels": _safe_list(hg.get("missing_node_labels") or hg.get("missing_key_nodes"))[:6],
        "similar_projects": _safe_list(hg.get("similar_projects"))[:4],
        "risk_patterns": _safe_list(hg.get("risk_patterns"))[:4],
        "suggested_evidence": _safe_list(hg.get("suggested_evidence"))[:5],
        "diagnosis_summary": {
            "conclusion": diagnosis_summary.get("conclusion"),
            "evidence": _safe_list(diagnosis_summary.get("evidence"))[:6],
            "findings": _safe_list(diagnosis_summary.get("findings"))[:6],
        },
        "provenance": {
            "node_sources": _safe_list(provenance.get("node_sources"))[:4],
            "hyperedge_evidence": _safe_list(provenance.get("hyperedge_evidence"))[:4],
        },
    }


def _render_hypergraph_prompt_block(
    hypergraph_context: dict[str, Any] | None,
    title: str = "以下是超图诊断结果，请把它当作辅助证据使用：",
) -> str:
    compact = _compact_hypergraph_context(hypergraph_context)
    if not compact.get("enabled") and not compact.get("matched_project", {}).get("name"):
        return ""
    matched_project = compact.get("matched_project") or {}
    matched_labels = [_stringify_value(item) for item in (compact.get("entity_match_stats") or {}).get("matched_labels") or []]
    alerts = [_stringify_value(item) for item in compact.get("consistency_alerts") or []]
    missing = [_stringify_value(item) for item in compact.get("missing_node_labels") or []]

    def _pick_field(item: Any, keys: list[str]) -> Any:
        if isinstance(item, dict):
            for key in keys:
                value = item.get(key)
                if _normalize_text(value):
                    return value
        return item

    similar = [_stringify_value(_pick_field(item, ["name", "project_name", "id"])) for item in compact.get("similar_projects") or []]
    suggested = [_stringify_value(_pick_field(item, ["text", "summary", "detail", "reason"])) for item in compact.get("suggested_evidence") or []]
    diagnosis = compact.get("diagnosis_summary") or {}
    evidence = [_stringify_value(item) for item in diagnosis.get("evidence") or []]
    return (
        f"\n{title}\n"
        f"- 匹配项目：{matched_project.get('name') or matched_project.get('id') or '暂无'}\n"
        f"- 命中节点：{', '.join([item for item in matched_labels if item]) or '暂无'}\n"
        f"- 一致性告警：{'；'.join([item for item in alerts if item]) or '暂无'}\n"
        f"- 缺失节点：{', '.join([item for item in missing if item]) or '暂无'}\n"
        f"- 相似项目：{'；'.join([item for item in similar if item]) or '暂无'}\n"
        f"- 建议补证：{'；'.join([item for item in suggested if item]) or '暂无'}\n"
        f"- 结论：{_stringify_value(diagnosis.get('conclusion')) or '暂无'}\n"
        f"- 依据：{'；'.join([item for item in evidence if item]) or '暂无'}\n"
        "请只把它当作辅助判断依据，不要机械复述字段名。\n"
    )


def _extract_json_block(text: str) -> dict[str, Any] | None:
    content = str(text or "").strip()
    if not content:
        return None
    fence_match = re.search(r"```json\s*(\{[\s\S]*\})\s*```", content, flags=re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(content[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _dedupe_text_list(values: list[Any], limit: int = 8) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        text = _normalize_text(item)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def _build_page_review_context(pages: list[dict[str, Any]], page_limit: int = 12, char_limit: int = 7200) -> str:
    lines: list[str] = []
    total = 0
    for page in pages[: max(page_limit, 1)]:
        page_no = int((page or {}).get("page", 1) or 1)
        text = _normalize_text((page or {}).get("text", ""))
        if not text:
            continue
        remaining = char_limit - total
        if remaining <= 0:
            break
        excerpt = text[: min(remaining, 780)]
        lines.append(f"[第{page_no}页]\n{excerpt}")
        total += len(excerpt)
    return "\n\n".join(lines)


def _normalize_dimension_name(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return "完整性"
    mapping = {
        "r1": "Problem Definition",
        "problem definition": "Problem Definition",
        "问题定义": "Problem Definition",
        "r2": "User Evidence Strength",
        "user evidence strength": "User Evidence Strength",
        "用户证据强度": "User Evidence Strength",
        "用户证据": "User Evidence Strength",
        "r3": "Solution Feasibility",
        "solution feasibility": "Solution Feasibility",
        "方案可行性": "Solution Feasibility",
        "解决方案可行性": "Solution Feasibility",
        "r4": "Business Model Consistency",
        "business model consistency": "Business Model Consistency",
        "商业模式一致性": "Business Model Consistency",
        "商业模式": "Business Model Consistency",
        "r5": "Market & Competition",
        "market & competition": "Market & Competition",
        "market and competition": "Market & Competition",
        "市场与竞争": "Market & Competition",
        "市场竞争": "Market & Competition",
        "r6": "Financial Logic",
        "financial logic": "Financial Logic",
        "财务逻辑": "Financial Logic",
        "财务": "Financial Logic",
        "r7": "Innovation & Differentiation",
        "innovation & differentiation": "Innovation & Differentiation",
        "innovation and differentiation": "Innovation & Differentiation",
        "创新与差异化": "Innovation & Differentiation",
        "差异化创新": "Innovation & Differentiation",
        "r8": "Team & Execution",
        "team & execution": "Team & Execution",
        "team and execution": "Team & Execution",
        "团队与执行": "Team & Execution",
        "团队执行": "Team & Execution",
        "r9": "Presentation & Material Quality",
        "presentation & material quality": "Presentation & Material Quality",
        "presentation and material quality": "Presentation & Material Quality",
        "呈现与材料质量": "Presentation & Material Quality",
        "材料质量": "Presentation & Material Quality",
        "创新": "创新点",
        "创新点": "创新点",
        "创新性": "创新点",
        "logic": "逻辑框架",
        "逻辑": "逻辑框架",
        "逻辑框架": "逻辑框架",
        "可行性": "可行性",
        "feasibility": "可行性",
        "完整性": "完整性",
        "completeness": "完整性",
        "大赛适配": "大赛适配",
        "competition": "大赛适配",
        "比赛适配": "大赛适配",
    }
    return mapping.get(text.lower(), mapping.get(text, text))


def _normalize_dimension_code(value: Any) -> str:
    name = _normalize_dimension_name(value)
    mapping = {
        "Problem Definition": "R1",
        "User Evidence Strength": "R2",
        "Solution Feasibility": "R3",
        "Business Model Consistency": "R4",
        "Market & Competition": "R5",
        "Financial Logic": "R6",
        "Innovation & Differentiation": "R7",
        "Team & Execution": "R8",
        "Presentation & Material Quality": "R9",
        "创新点": "innovation",
        "逻辑框架": "logic",
        "可行性": "feasibility",
        "完整性": "completeness",
        "大赛适配": "competition",
    }
    raw = _normalize_text(value).upper()
    if raw in {f"R{idx}" for idx in range(1, 10)}:
        return raw
    return mapping.get(name, "completeness")


def _normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        return 0.0
    if score > 5.0:
        score = score / 20.0 if score <= 100 else score
    return round(_clamp(score, 1.0, 5.0), 2)


def _is_hypergraph_only_text(text: Any) -> bool:
    content = _normalize_text(text)
    if not content:
        return False
    technical_tokens = ["超图", "超边", "节点", "一致性风险", "结构诊断", "知识图谱"]
    if not any(token in content for token in technical_tokens):
        return False
    readable_tokens = ["文档", "方案", "项目书", "计划书", "页", "段", "市场", "用户", "痛点", "方案", "验证", "商业模式"]
    return not any(token in content for token in readable_tokens)


def _normalize_issue_record(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        item = {"description": item}
    if not isinstance(item, dict):
        return None

    description = _normalize_text(
        item.get("description")
        or item.get("issue")
        or item.get("problem")
        or item.get("title")
        or item.get("text")
    )
    if not description or _is_hypergraph_only_text(description):
        return None

    question = _normalize_text(
        item.get("question")
        or item.get("guiding_question")
        or item.get("prompt_question")
        or "如果评委追问这一处，你现在能拿出什么证据或论证来回答？"
    )
    if question and not question.endswith(("？", "?")):
        question = f"{question}？"

    evidence = _normalize_text(
        item.get("evidence")
        or item.get("reason")
        or item.get("basis")
        or item.get("why")
        or item.get("analysis")
    )
    snippet = _normalize_text(item.get("snippet") or item.get("anchor") or item.get("quote"))
    dimension = _normalize_dimension_name(item.get("dimension") or item.get("label") or item.get("category"))
    code = _normalize_dimension_code(item.get("code") or dimension)

    page = 0
    paragraph = 0
    try:
        page = int(item.get("page") or 0)
    except Exception:
        page = 0
    try:
        paragraph = int(item.get("paragraph") or 0)
    except Exception:
        paragraph = 0

    risk_level = str(item.get("risk_level") or item.get("severity") or "").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = _infer_risk_level(description)

    normalized = {
        "dimension": dimension,
        "code": code,
        "category": _normalize_text(item.get("category") or code),
        "description": description,
        "question": question,
        "risk_level": risk_level,
        "evidence": evidence,
        "snippet": snippet,
        "anchor": snippet or description[:16],
        "page": page,
        "paragraph": paragraph,
        "start": _safe_int(item.get("start"), -1),
        "end": _safe_int(item.get("end"), -1),
        "source": "document",
    }
    return normalized


def _normalize_annotation_record(item: Any) -> dict[str, Any] | None:
    normalized = _normalize_issue_record(item)
    if not normalized:
        return None
    description = _normalize_text(
        (item or {}).get("description")
        or (item or {}).get("comment")
        or normalized.get("description")
    )
    if not description or _is_hypergraph_only_text(description):
        return None
    normalized["description"] = description
    return normalized


def _normalize_dimension_scores(payload: dict[str, Any], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = payload.get("dimension_scores") or payload.get("scores") or []
    normalized: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, str):
            continue
        label = _normalize_dimension_name((item or {}).get("label") or (item or {}).get("dimension") or (item or {}).get("name") or (item or {}).get("code"))
        code = _normalize_dimension_code((item or {}).get("code") or label)
        score = _normalize_score((item or {}).get("score") or (item or {}).get("value") or (item or {}).get("rating"))
        weight = 20.0
        for row in fallback_rows:
            if str(row.get("code") or "").lower() == code:
                weight = float(row.get("weight") or 20)
                break
        reason = _normalize_text((item or {}).get("reason") or (item or {}).get("comment") or (item or {}).get("analysis"))
        normalized.append(
            {
                "code": code,
                "label": label,
                "weight": weight,
                "score": score or 3.0,
                "max_score": 5,
                "weighted_score": round(weight * (score or 3.0) / 5.0, 2),
                "reason": reason or "该维度已给出综合判断，但仍建议结合文档原文继续校准。",
            }
        )

    if not normalized:
        return fallback_rows

    by_code = {str(item.get("code") or "").lower(): item for item in normalized}
    merged: list[dict[str, Any]] = []
    for row in fallback_rows:
        code = str(row.get("code") or "").lower()
        merged.append(by_code.get(code, row))
    return merged


def _render_review_summary(summary_payload: Any, fallback_summary: str = "") -> str:
    if isinstance(summary_payload, str):
        content = _normalize_text(summary_payload)
        return content or fallback_summary
    if isinstance(summary_payload, (list, tuple)):
        lines = [_normalize_text(item) for item in summary_payload if _normalize_text(item)]
        if not lines:
            return fallback_summary
        return "## 补充分析评审要点\n" + "\n".join([f"- {item}" for item in lines[:6]])
    if not isinstance(summary_payload, dict):
        return fallback_summary

    highlight_rows = _safe_list(
        summary_payload.get("highlights")
        or summary_payload.get("core_highlights")
        or summary_payload.get("strengths")
    )
    problem_rows = _safe_list(
        summary_payload.get("problems")
        or summary_payload.get("issues")
        or summary_payload.get("to_improve")
    )
    guidance_rows = _safe_list(
        summary_payload.get("guidance")
        or summary_payload.get("optimization_guidance")
        or summary_payload.get("suggestions")
    )

    def _as_statement(items: list[Any], kind: str, limit: int = 3, max_len: int = 220) -> str:
        rows: list[str] = []
        for idx, item in enumerate(items[:limit], start=1):
            if isinstance(item, str):
                text = _normalize_text(item)
            elif isinstance(item, dict):
                if kind == "highlight":
                    text = _normalize_text(item.get("conclusion") or item.get("point") or item.get("title"))
                elif kind == "problem":
                    text = _normalize_text(item.get("conclusion") or item.get("problem") or item.get("title"))
                else:
                    text = _normalize_text(item.get("direction") or item.get("conclusion") or item.get("title") or item.get("question"))
            else:
                text = ""
            if text:
                rows.append(f"{idx}）{text}")
        combined = " ".join(rows).strip()
        return _truncate(combined, max_len) if combined else ""

    overall = _as_statement(highlight_rows, "highlight", limit=2, max_len=180) or "项目已有一定基础，但当前材料的说服力和完整度仍需继续增强。"
    core_problem = _as_statement(problem_rows, "problem", limit=3, max_len=240) or "当前未提取到明确核心问题，建议结合批注继续核对论证链。"
    direction = _as_statement(guidance_rows, "guidance", limit=3, max_len=240) or "优先补齐能直接支撑评委判断的关键证据，再完善市场、商业模式和落地路径。"
    competition_advice = "答辩或路演时，优先讲清“你解决什么问题、为什么现在能做、凭什么赢”，避免只讲技术细节不讲商业价值。"

    lines = ["## 补充分析评审要点"]
    lines.append(f"- **总体评价：** {overall}")
    lines.append(f"- **核心问题：** {core_problem}")
    lines.append(f"- **改进方向：** {direction}")
    lines.append(f"- **大赛适配性建议：** {competition_advice}")

    summary = "\n".join(lines).strip()
    return summary or fallback_summary


def _build_examples(missing_parts: list[dict[str, str]], issues: list[dict[str, Any]]) -> list[str]:
    examples: list[str] = []
    for item in missing_parts[:3]:
        key = item.get("key")
        if key == "validation":
            examples.append("示例：补充10-20位目标用户访谈，标明高频痛点、样本量和原话证据。")
        elif key == "business":
            examples.append("示例：列出客户、收费方式、核心成本项和回本假设之间的对应关系。")
        elif key == "plan":
            examples.append("示例：按阶段列出里程碑、负责人、资源需求和风险预案。")
        elif key == "problem":
            examples.append("示例：用一句话讲清具体用户、具体场景和具体痛点。")
        else:
            examples.append(f"示例：围绕“{item.get('part') or '关键内容'}”补一段论证，并配一条可追溯证据。")
    if not examples and issues:
        for item in issues[:2]:
            anchor = _normalize_text(item.get("snippet") or item.get("anchor") or item.get("description"))
            if anchor:
                examples.append(f"示例：围绕“{_truncate(anchor, 26)}”补充一条数据、访谈原话或试点结果。")
    return _dedupe_text_list(examples, limit=4)


def _build_review_llm_prompt(
    pages: list[dict[str, Any]],
    audience_role: str,
    project_type: str,
    hypergraph_context: dict[str, Any] | None,
    missing_parts: list[dict[str, str]],
    logic_result: dict[str, Any],
    fallback_scores: list[dict[str, Any]],
    material_state: dict[str, Any],
) -> str:
    page_context = _build_page_review_context(pages)
    role_note = str(audience_role or "student")
    project_rule = (
        "项目类型=公益：请关注社会问题定义、受益人证据、影响评估、可持续运营机制。"
        if project_type == "public_welfare"
        else "项目类型=商业：请关注市场规模、客户价值、盈利路径、增长与现金流。"
    )
    case_patterns = _load_case_patterns(limit=2, score_tag="完整性")
    scene_prompt = _load_scene_prompt("student_pdf_review", "default", case_patterns)
    hypergraph_block = _render_hypergraph_prompt_block(
        hypergraph_context,
        title="以下是超图辅助诊断，只能作为辅助证据，不得直接变成“超图提示/节点缺失/超边风险”这类展示文本：",
    )
    rubric_outline = [
        {
            "code": row.get("code"),
            "label": row.get("label"),
            "weight": row.get("weight"),
            "prompt_hint": row.get("reason") or row.get("prompt_hint") or "",
        }
        for row in fallback_scores
    ]
    completion_note = (
        "当前材料更像项目半成品或未完成版本，请重点识别缺失部分、未展开部分和需要补齐的关键论证。"
        if material_state.get("is_partial_project")
        else "当前材料已具备基础项目书结构，请同时覆盖基础检阅与深度检阅。"
    )
    return (
        "你是创新创业大赛评委兼导师。请完整阅读以下创业计划书全文，并返回JSON。\n"
        "检阅要求：\n"
        "1) 检阅主体必须来自文档原文，先看文档内容，再结合辅助信息判断。\n"
        "2) 要同时覆盖基础检阅与深度检阅。基础检阅看错别字、语病、表达与结构；深度检阅看逻辑闭环、可行性、创新独特性、完整性和大赛适配性。\n"
        "3) 如果材料属于创新创业项目但完成度不足，不能判定为无关内容，而要明确指出目前缺哪些关键模块。\n"
        "4) 超图信息只能作为辅助证据，不能把“超图节点”“超边”“一致性风险”这类技术词直接写进批注或问题描述。\n"
        "5) 所有问题和批注都要写成人能看懂的语言，并用引导式提问，不直接代写。\n"
        "6) 结论必须细致，写清楚判断依据。\n"
        "输出建议：优先返回 JSON 对象，字段顺序与分组不要求固定。\n"
        "至少包含 issues、guidance_questions、summary 三类内容；可补充 annotations、dimension_scores、suggestions、examples。\n"
        "内容约束：\n"
        "1) issues 数量不设上限，按实际问题输出；\n"
        "2) 每条 issue 尽量给 page 和 snippet，能定位则补 start/end（相对该页文本）；\n"
        "3) 问题应覆盖逻辑闭环、可行性、创新独特性、完整性、大赛适配性及必要表达问题；\n"
        "4) question 使用引导式表达，不直接代写；\n"
        "5) risk_level 使用 low/medium/high；\n"
        "6) summary 用多条结论概括，并写清判断依据。\n"
        f"\n补充规则：{project_rule}"
        f"\n受众角色: {role_note}"
        f"\n基础规则：{PROMPT_POLICY.get(audience_role, PROMPT_POLICY['student'])}"
        f"\n材料状态提示：{completion_note}"
        f"\n场景提示：{scene_prompt}"
        f"\n材料判定：{json.dumps(material_state, ensure_ascii=False)}"
        f"\n启发式缺失部分：{json.dumps(missing_parts[:6], ensure_ascii=False)}"
        f"\n启发式逻辑问题：{json.dumps((logic_result.get('issues') or [])[:6], ensure_ascii=False)}"
        f"\n启发式评分参考：{json.dumps(rubric_outline, ensure_ascii=False)}"
        f"{hypergraph_block}"
        f"\n全文内容：\n{page_context}\n"
    )


def _llm_review_payload(
    pages: list[dict[str, Any]],
    audience_role: str,
    hypergraph_context: dict[str, Any] | None,
    project_type: str,
    missing_parts: list[dict[str, str]],
    logic_result: dict[str, Any],
    fallback_scores: list[dict[str, Any]],
    fallback_summary: str,
    material_state: dict[str, Any],
) -> dict[str, Any] | None:
    prompt = _build_review_llm_prompt(
        pages=pages,
        audience_role=audience_role,
        project_type=project_type,
        hypergraph_context=hypergraph_context,
        missing_parts=missing_parts,
        logic_result=logic_result,
        fallback_scores=fallback_scores,
        material_state=material_state,
    )
    llm_result = _call_llm(
        prompt,
        timeout_seconds=LLM_REVIEW_TIMEOUT_SECONDS,
        system_prompt=PDF_REVIEW_SYSTEM_PROMPT,
    )
    payload = _extract_json_block(llm_result or "")
    if not payload:
        return None

    normalized_issues = []
    for item in payload.get("issues") or []:
        row = _normalize_issue_record(item)
        if row:
            normalized_issues.append(row)
    normalized_issues = _dedupe_issues(normalized_issues)[:10]

    normalized_annotations = []
    for item in payload.get("annotations") or []:
        row = _normalize_annotation_record(item)
        if row:
            normalized_annotations.append(row)
    normalized_annotations = _dedupe_issues(normalized_annotations)[:12]

    if not normalized_issues and not normalized_annotations:
        return None

    guidance_questions = _dedupe_text_list(
        list(payload.get("guidance_questions") or [])
        + [item.get("question", "") for item in normalized_issues[:6]]
        + [item.get("question", "") for item in normalized_annotations[:6]],
        limit=8,
    )
    suggestions = _dedupe_text_list(payload.get("suggestions") or [], limit=8)
    examples = _dedupe_text_list(payload.get("examples") or [], limit=4)
    dimension_scores = _normalize_dimension_scores(payload, fallback_scores)
    summary = _render_review_summary(payload.get("summary"), fallback_summary=fallback_summary)

    return {
        "issues": normalized_issues,
        "annotations": normalized_annotations,
        "guidance_questions": guidance_questions,
        "suggestions": suggestions,
        "examples": examples,
        "dimension_scores": dimension_scores,
        "summary": summary,
    }


def _compute_missing_parts(text: str) -> list[dict[str, str]]:
    missing_parts = _detect_completeness(text).get("missing_parts") or []
    return [dict(item) for item in missing_parts]


def _section_coverage(text: str) -> dict[str, bool]:
    return {key: _section_present(key, text) for key in COMPLETENESS_SECTIONS}


def validate_logic(text: str) -> dict[str, Any]:
    content = _normalize_text(text)
    missing_parts = _compute_missing_parts(content)
    issues: list[str] = []

    if _contains_any(content, ["用户", "客户", "画像"]) and not _contains_any(content, ["痛点", "问题", "需求"]):
        issues.append("已经提到目标用户，但用户面对的核心痛点还没有被清楚定义。")
    if _contains_any(content, ["痛点", "问题", "需求"]) and not _contains_any(content, ["方案", "产品", "服务"]):
        issues.append("说明了问题，但没有给出对应的解决方案或产品机制。")
    if _contains_any(content, ["方案", "产品", "服务"]) and not _contains_any(content, ["验证", "访谈", "问卷", "试点", "数据", "反馈"]):
        issues.append("提出了解决方案，但缺少验证证据，评委难以判断方案是否真实有效。")
    if _contains_any(content, ["收入", "盈利", "付费", "商业模式"]) and not _contains_any(content, ["成本", "费用", "投入"]):
        issues.append("提到了收入或盈利，但没有说明成本结构，商业闭环仍然不完整。")
    if _contains_any(content, ["计划", "里程碑", "时间表"]) and not _contains_any(content, ["团队", "分工", "负责人", "资源"]):
        issues.append("写了实施计划，但还没有对应到团队分工、资源配置或负责人。")
    if _contains_any(content, ["市场", "需求", "效果", "可行性"]) and not _has_number(content):
        issues.append("关键判断缺少数字、比例、样本量或测算结果，证据说服力偏弱。")

    suggestions = []
    if missing_parts:
        missing_text = "、".join(item["part"] for item in missing_parts[:5])
        suggestions.append(f"你能否先补齐这几个关键部分：{missing_text}？")
    suggestions.append("你能否按“痛点→方案→验证→盈利模式→实施计划”的顺序重新检查主线是否闭环？")
    suggestions.append("每一条关键判断后面，你是否都能补上一条数据、访谈原话或试点结果？")
    if not _has_number(content):
        suggestions.append("如果评委要求你量化项目判断，你现在最先能补哪三组数字？")

    summary = "当前文档已有项目基础，但论证链条还存在若干证据和结构缺口。"
    if not issues and not missing_parts:
        summary = "当前文档主线基本成立，后续重点应放在证据增强和表达打磨。"

    return {
        "passed": not issues and not missing_parts,
        "issues": issues,
        "missing_parts": missing_parts,
        "suggestions": suggestions,
        "summary": summary,
    }


def _dimension_score_for_key(
    key: str,
    text: str,
    coverage: dict[str, bool],
    missing_parts: list[dict[str, str]],
    logic_result: dict[str, Any],
    hypergraph_context: dict[str, Any] | None = None,
) -> tuple[float, str]:
    content = str(text or "")
    missing_count = len(missing_parts)
    logic_penalty = len(logic_result.get("issues") or [])
    metrics = (hypergraph_context or {}).get("metrics") or {}
    coverage_rate = float(metrics.get("label_coverage_rate") or 0)
    boost = min(0.35, coverage_rate / 320.0)

    if key == "innovation":
        score = 2.2
        if _contains_any(content, ["创新", "差异化", "独特", "壁垒", "专利", "首创", "独有"]):
            score += 1.0
        if _contains_any(content, ["竞品", "替代方案", "对比", "相较于", "区别于"]):
            score += 0.8
        if coverage.get("problem") and coverage.get("solution"):
            score += 0.4
        reason = "重点看创新点是否明确、是否说明与现有方案的差异，并且是否真正对应行业痛点。"
    elif key == "logic":
        covered = sum(1 for hit in coverage.values() if hit)
        score = 1.7 + covered * 0.42 - logic_penalty * 0.22
        if _contains_any(content, ["因此", "所以", "基于", "从而", "闭环"]):
            score += 0.4
        reason = "重点看痛点、方案、盈利模式和实施计划是否前后连贯、没有明显断裂。"
    elif key == "feasibility":
        score = 2.0
        if coverage.get("plan"):
            score += 0.7
        if _contains_any(content, ["成本", "资源", "试点", "mvp", "团队", "风险", "落地"]):
            score += 1.0
        if _has_number(content):
            score += 0.3
        reason = "重点看是否考虑资源、成本、落地节奏和风险，不只是停留在概念层面。"
    elif key == "completeness":
        covered = sum(1 for hit in coverage.values() if hit)
        score = 1.8 + covered * 0.45 - missing_count * 0.15
        if len(content) > 1200:
            score += 0.3
        reason = "重点看关键环节是否齐全，是否存在明显缺少的重要模块。"
    elif key == "competition":
        score = 2.1
        if _contains_any(content, ["市场", "竞品", "评审", "用户价值", "社会价值", "行业"]):
            score += 0.9
        if _contains_any(content, ["数据", "案例", "样本", "访谈", "验证"]):
            score += 0.8
        reason = "重点看是否覆盖评委高频关注点，例如市场、竞品、证据和项目亮点。"
    else:
        score = 2.0 + sum(1 for hit in coverage.values() if hit) * 0.4 - missing_count * 0.15
        reason = "综合看结构、证据与可执行性。"

    score = round(_clamp(score + boost, 1.0, 5.0), 2)
    return score, reason


def _build_dimension_scores(text: str, hypergraph_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    coverage = _section_coverage(text)
    missing_parts = _compute_missing_parts(text)
    logic_result = validate_logic(text)
    rows = []
    for item in _load_rubrics():
        code = str(item.get("code") or "").strip().lower()
        score, reason = _dimension_score_for_key(
            code,
            text,
            coverage,
            missing_parts,
            logic_result,
            hypergraph_context=hypergraph_context,
        )
        weight = float(item.get("weight") or 20)
        rows.append(
            {
                "code": code or "dimension",
                "label": item.get("label") or code or "维度",
                "weight": weight,
                "score": score,
                "max_score": 5,
                "weighted_score": round(weight * score / 5.0, 2),
                "reason": f"{reason} 当前判断约为 {score}/5。",
            }
        )
    return rows


def _build_rubric_fallback_scores(text: str, hypergraph_context: dict[str, Any] | None = None) -> dict[str, Any]:
    base_rows = _build_dimension_scores(text, hypergraph_context=hypergraph_context)
    base_map = {str(item.get("code") or "").lower(): item for item in base_rows}
    coverage = _section_coverage(text)
    rows: list[dict[str, Any]] = []
    weight = 5.0 / max(len(RUBRIC_9_DIMENSIONS), 1)
    bindings = [
        ("R1", "Problem Definition", "logic", "问题定义还需要进一步收紧，建议明确项目究竟在解决哪个具体问题。"),
        ("R2", "User Evidence Strength", "completeness", "用户证据仍然偏弱，建议补充访谈、样本或问卷等直接支撑。"),
        ("R3", "Solution Feasibility", "feasibility", "方案基本可理解，但资源、成本与落地路径还需要更细化。"),
        ("R4", "Business Model Consistency", "logic", "商业闭环还不够稳定，建议继续核对价值、收费对象和收费方式是否一致。"),
        ("R5", "Market & Competition", "competition", "市场和竞品分析还需要更具体，特别是目标市场规模和替代方案对比。"),
        ("R6", "Financial Logic", "feasibility", "财务假设需要更自洽，建议明确收入、成本、现金流之间的关系。"),
        ("R7", "Innovation & Differentiation", "innovation", "创新点已有基础，但差异化和独特性表达仍可更明确。"),
        ("R8", "Team & Execution", "completeness", "团队与执行安排需要再补细节，建议说明角色分工和推进节奏。"),
        ("R9", "Presentation & Material Quality", "completeness", "材料结构基本成形，但表达效率、排版与重点突出度还可优化。"),
    ]

    for code, label, source_code, default_reason in bindings:
        source = base_map.get(source_code) or {}
        score = float(source.get("score") or 3.0)
        if code == "R2" and not coverage.get("validation"):
            score -= 0.8
        if code == "R4" and not coverage.get("business"):
            score -= 0.6
        if code == "R6" and not _contains_any(text, ["财务", "预算", "收入", "成本", "利润", "现金流"]):
            score -= 0.9
        if code == "R8" and not _contains_any(text, ["团队", "成员", "分工", "负责人", "执行"]):
            score -= 0.5
        if code == "R9" and len(_normalize_text(text)) < 900:
            score -= 0.4
        score = round(_clamp(score, 1.0, 5.0), 2)
        reason = _normalize_text(source.get("reason")) or default_reason
        rows.append(
            {
                "code": code,
                "label": label,
                "weight": weight,
                "score": score,
                "max_score": 5.0,
                "weighted_score": round(score / max(len(RUBRIC_9_DIMENSIONS), 1), 2),
                "reason": reason,
                "suggestion": "",
            }
        )

    average_score = round(sum(float(item.get("score") or 0) for item in rows) / max(len(rows), 1), 2)
    return {
        "dimensions": rows,
        "total_score": average_score,
        "max_score": 5.0,
        "overall_summary": "Rubric 评分已按启发式规则生成，建议结合文档原文继续人工复核。",
    }


def _llm_rubric_scores(
    text: str,
    hypergraph_context: dict[str, Any] | None = None,
    project_type: str = "commercial",
) -> dict[str, Any]:
    fallback = _build_rubric_fallback_scores(text, hypergraph_context=hypergraph_context)
    dimension_prompt = "\n".join([f"- {idx + 1}. {name}" for idx, name in enumerate(RUBRIC_9_DIMENSIONS)])
    hypergraph_block = _render_hypergraph_prompt_block(
        hypergraph_context,
        title="以下是基于超图知识库的诊断结果，请参考这些信息给出反馈：",
    )
    project_rule = (
        "项目类型=公益：重点关注社会影响、受益人覆盖、可持续运营与伦理风险。"
        if project_type == "public_welfare"
        else "项目类型=商业：重点关注市场规模、增长路径、盈利与现金流自洽。"
    )
    prompt = (
        "你是一位资深的创新创业项目评审专家。"
        "请严格按九项维度做1-5分评分，并仅输出JSON。"
        "输出格式："
        "{\"scores\":[{\"dimension\":\"Problem Definition\",\"score\":0-5,\"comment\":\"\",\"suggestion\":\"\"}],"
        "\"overall_summary\":\"\",\"average_score\":0.0}。"
        "要求："
        "1) 必须覆盖九个维度且维度名准确；"
        "2) comment用中文简短评语；"
        "3) suggestion可为空；"
        "4) 不要输出JSON外任何文本。"
        f"\n补充规则：{project_rule}"
        f"\n九项维度：\n{dimension_prompt}"
        f"\n项目文本：{(text or '')[:3000]}"
        f"{hypergraph_block}"
    )
    content = _call_llm(prompt, timeout_seconds=120, system_prompt=TEACHER_REVIEW_PROMPT)
    payload = _extract_json_block(content or "")
    if not payload:
        return fallback

    raw_rows = payload.get("scores") or []
    if not isinstance(raw_rows, list):
        return fallback

    normalized_rows: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_rows, start=1):
        if not isinstance(item, dict):
            continue
        label = _normalize_dimension_name(item.get("dimension") or item.get("label") or item.get("name") or f"R{idx}")
        code = _normalize_dimension_code(item.get("code") or label or f"R{idx}")
        if code not in {f"R{i}" for i in range(1, len(RUBRIC_9_DIMENSIONS) + 1)}:
            continue
        score = _normalize_score(item.get("score"))
        if score <= 0:
            continue
        normalized_rows.append(
            {
                "code": code,
                "label": label,
                "weight": 5.0 / max(len(RUBRIC_9_DIMENSIONS), 1),
                "score": score,
                "max_score": 5.0,
                "weighted_score": round(score / max(len(RUBRIC_9_DIMENSIONS), 1), 2),
                "reason": _normalize_text(item.get("comment")) or "评估完成。",
                "suggestion": _normalize_text(item.get("suggestion")),
            }
        )

    if not normalized_rows:
        return fallback

    merged_map = {str(item.get("code") or ""): item for item in normalized_rows}
    merged_dimensions = []
    for fallback_row in fallback.get("dimensions") or []:
        merged_dimensions.append(merged_map.get(str(fallback_row.get("code") or ""), fallback_row))

    average_score = payload.get("average_score")
    try:
        average_score = float(average_score)
    except Exception:
        average_score = 0.0
    if average_score <= 0:
        average_score = round(sum(float(item.get("score") or 0) for item in merged_dimensions) / max(len(merged_dimensions), 1), 2)

    return {
        "dimensions": merged_dimensions,
        "total_score": round(average_score, 2),
        "max_score": 5.0,
        "overall_summary": _normalize_text(payload.get("overall_summary")),
    }


def rubric_agent_score(
    text: str,
    hypergraph_context: dict[str, Any] | None = None,
    project_type: str = "commercial",
) -> dict[str, Any]:
    return _llm_rubric_scores(text, hypergraph_context=hypergraph_context, project_type=project_type)


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in issues:
        description = _normalize_text(item.get("description"))
        question = _normalize_text(item.get("question"))
        key = (description, question)
        if not description or key in seen:
            continue
        seen.add(key)
        normalized = dict(item)
        normalized["description"] = description
        normalized["question"] = question
        normalized["risk_level"] = normalized.get("risk_level") or _infer_risk_level(description)
        normalized["evidence"] = _normalize_text(normalized.get("evidence"))
        normalized["source"] = str(normalized.get("source") or "document").strip().lower()
        result.append(normalized)
    return result


def _missing_part_issue(item: dict[str, str]) -> dict[str, Any]:
    config = COMPLETENESS_SECTIONS.get(item.get("key") or "", {})
    part = item.get("part") or "关键内容"
    return {
        "dimension": "完整性",
        "category": item.get("key") or "missing_part",
        "description": f"缺少“{part}”相关内容，评委很难判断这一部分是否成立。",
        "question": config.get("question") or f"如果评委追问“{part}”这一块，你现在能拿出什么说明或证据？",
        "risk_level": "high" if item.get("urgency") == "high" else "medium",
        "anchor": part,
        "evidence": f"当前文档中没有识别到与“{part}”相关的稳定论证。",
        "source": "document",
    }


def _build_issues(
    text: str,
    missing_parts: list[dict[str, str]],
    logic_result: dict[str, Any],
    dimension_scores: list[dict[str, Any]],
    hypergraph_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    content = str(text or "")
    score_map = {str(item.get("code") or ""): item for item in dimension_scores}

    for item in missing_parts:
        issues.append(_missing_part_issue(item))

    for detail in logic_result.get("issues") or []:
        issues.append(
            {
                "dimension": "逻辑框架",
                "category": "logic",
                "description": detail,
                "question": "如果评委要求你把前后逻辑讲成一条完整链路，你最需要补哪一个前提或证据？",
                "risk_level": _infer_risk_level(detail),
                "anchor": detail[:12],
                "evidence": "该判断来自文档主线扫描，发现上下游论证没有完全闭合。",
                "source": "document",
            }
        )

    innovation_score = float((score_map.get("innovation") or {}).get("score") or 0)
    if innovation_score < 3.2:
        issues.append(
            {
                "dimension": "创新点",
                "category": "innovation",
                "description": "创新点表述还不够清晰，目前更像一般性功能描述，独特性和痛点对应关系不够强。",
                "question": "如果评委追问“你的创新到底新在哪里”，你能否用一条对比关系说清楚？",
                "risk_level": "medium",
                "anchor": "创新",
                "evidence": "文档中缺少稳定的差异化表述、替代方案对比或独特机制说明。",
                "source": "document",
            }
        )

    feasibility_score = float((score_map.get("feasibility") or {}).get("score") or 0)
    if feasibility_score < 3.1:
        issues.append(
            {
                "dimension": "可行性",
                "category": "feasibility",
                "description": "可行性论证偏弱，成本、资源、落地路径或风险应对没有被充分说明。",
                "question": "如果评委追问“这个项目凭什么能做出来”，你现在最先能补哪一类落地依据？",
                "risk_level": "medium",
                "anchor": "落地",
                "evidence": "文档中关于成本、资源配置、试点路径或风险预案的说明不足。",
                "source": "document",
            }
        )

    competition_score = float((score_map.get("competition") or {}).get("score") or 0)
    if competition_score < 3.2:
        issues.append(
            {
                "dimension": "大赛适配",
                "category": "competition",
                "description": "大赛适配度还不够强，市场、竞品、证据或项目亮点中至少有一项支撑不足。",
                "question": "如果评委从市场空间、竞品优势和证据链里选一个追问，你最担心哪一项？",
                "risk_level": "medium",
                "anchor": "竞品",
                "evidence": "文档对市场、竞品、评审亮点和证据支撑的覆盖仍不够完整。",
                "source": "document",
            }
        )

    if len(content) < 450:
        issues.append(
            {
                "dimension": "完整性",
                "category": "length",
                "description": "文档信息密度偏低，很多关键判断还没有展开到评委可直接理解的程度。",
                "question": "如果你只能优先补三部分内容，哪三部分最能提升评委理解效率？",
                "risk_level": "medium",
                "anchor": "项目",
                "evidence": f"当前可解析文本长度约 {len(content)} 个字符。",
                "source": "document",
            }
        )

    if not _has_number(content):
        issues.append(
            {
                "dimension": "可行性",
                "category": "evidence",
                "description": "文档几乎没有量化信息，评委很难判断需求强度、验证质量和落地可信度。",
                "question": "如果必须补三组数字来支撑项目判断，你最先会补哪三组？",
                "risk_level": "medium",
                "anchor": "数据",
                "evidence": "全文中几乎没有识别到样本量、比例、成本、收入或试点结果等数字信息。",
                "source": "document",
            }
        )

    deduped = _dedupe_issues(issues)
    return deduped[:10]


def _build_annotations(pages: list[dict[str, Any]], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotations = []
    page_rows = pages or [{"page": 1, "text": ""}]
    page_map = {int((item or {}).get("page", 0) or 0): item for item in page_rows}
    for index, issue in enumerate(issues):
        if str(issue.get("source") or "document").lower() != "document":
            continue
        if _is_hypergraph_only_text(issue.get("description")):
            continue

        preferred_page = page_map.get(int(issue.get("page") or 0))
        matched_page = preferred_page or page_rows[min(index, len(page_rows) - 1)]
        best_start, best_end, best_snippet = 0, 0, ""

        precise_span = _resolve_precise_span((matched_page or {}).get("text", ""), issue)
        if precise_span:
            best_start, best_end, best_snippet = precise_span
        else:
            best_start, best_end, best_snippet = _find_span((matched_page or {}).get("text", ""), issue, index)
            scan_rows = [preferred_page] if preferred_page else []
            scan_rows.extend([page for page in page_rows if page is not preferred_page])
            for page in scan_rows:
                if not page:
                    continue
                precise_span = _resolve_precise_span((page or {}).get("text", ""), issue)
                if precise_span:
                    matched_page = page
                    best_start, best_end, best_snippet = precise_span
                    break
                start, end, snippet = _find_span((page or {}).get("text", ""), issue, index)
                if snippet:
                    matched_page = page
                    best_start, best_end, best_snippet = start, end, snippet
                    break

        page_text = str((matched_page or {}).get("text", "") or "")
        page_length = max(len(page_text), 1)
        snippet_length = max(best_end - best_start, len(best_snippet), 18)
        ratio = round(best_start / page_length, 3)
        span_ratio = round(_clamp(snippet_length / page_length, 0.05, 0.34), 3)
        paragraph = int(issue.get("paragraph") or 0) or _estimate_paragraph_index(page_text, best_start)
        risk_level = issue.get("risk_level") or _infer_risk_level(issue.get("description", ""))
        description = issue.get("description", "待完善")
        question = issue.get("question", "如果评委追问这一部分，你现在能如何证明它成立？")
        page_no = int(issue.get("page") or 0) or int((matched_page or {}).get("page", 1) or 1)

        annotations.append(
            {
                "page": page_no,
                "paragraph": paragraph,
                "start": best_start,
                "end": best_end,
                "ratio": ratio,
                "span_ratio": span_ratio,
                "y_ratio": ratio,
                "left_ratio": 0.05,
                "width_ratio": round(_clamp(0.24 + span_ratio * 0.75, 0.18, 0.84), 3),
                "height_ratio": round(_clamp(0.06 + span_ratio * 0.28, 0.05, 0.24), 3),
                "snippet": best_snippet or issue.get("anchor") or description,
                "description": description,
                "question": question,
                "formatted": f"【页码{page_no}，段落{paragraph}】{description} 引导提问：{question}",
                "risk_level": risk_level,
                "risk_color": RISK_COLOR_MAP.get(risk_level, RISK_COLOR_MAP["low"]),
                "font_color": "#ffffff",
            }
        )
    return annotations


def _build_strengths(text: str, coverage: dict[str, bool], hypergraph_context: dict[str, Any] | None = None) -> list[str]:
    strengths = []
    if coverage.get("problem") and coverage.get("solution"):
        strengths.append("已经建立“问题—方案”主线，项目主题不是空泛口号。")
    if coverage.get("validation"):
        strengths.append("文档中已经出现调研或验证意识，不完全停留在主观判断。")
    if coverage.get("business"):
        strengths.append("已经开始讨论商业或运营闭环，具备进一步打磨基础。")
    if coverage.get("plan"):
        strengths.append("已有实施计划或落地安排，说明项目具有推进意识。")
    compact_hg = _compact_hypergraph_context(hypergraph_context)
    matched_project = compact_hg.get("matched_project") or {}
    if matched_project.get("name"):
        strengths.append(f"超图已能匹配到相关项目结构，说明项目主线具备一定可识别性。")
    deduped = []
    for item in strengths:
        if item not in deduped:
            deduped.append(item)
    return deduped[:2]


def _build_guidance_block(issues: list[dict[str, Any]], missing_parts: list[dict[str, str]]) -> list[str]:
    guidance = []
    if missing_parts:
        missing_text = "、".join(item["part"] for item in missing_parts[:3])
        guidance.append(f"你是否可以先补清 {missing_text}，再回头检查整条主线是否闭环？")
    for item in issues[:2]:
        question = _truncate(item.get("question"), 54)
        if question and question not in guidance:
            guidance.append(question)
    if not guidance:
        guidance.append("如果评委只问你一个最核心的问题，你最需要先补哪一条证据来回答？")
    return guidance[:3]


def _compose_summary(
    strengths: list[str],
    issues: list[dict[str, Any]],
    missing_parts: list[dict[str, str]],
    hypergraph_context: dict[str, Any] | None = None,
) -> str:
    core_highlights = strengths or ["当前文档已经具备项目主线基础，但仍需要进一步增强说服力。"]
    top_issues = issues[:3]
    guidance = _build_guidance_block(issues, missing_parts)
    compact_hg = _compact_hypergraph_context(hypergraph_context)
    hg_conclusion = _truncate((compact_hg.get("diagnosis_summary") or {}).get("conclusion"), 72)

    overall = _truncate("；".join(core_highlights[:2]), 180)
    core_problem = _truncate(
        " ".join(
            [f"{idx + 1}）{_normalize_text(item.get('description'))}" for idx, item in enumerate(top_issues[:3]) if _normalize_text(item.get("description"))]
        ) or "当前未发现明显结构性缺口，后续重点可放在证据增强与表达打磨。",
        260,
    )
    direction = _truncate(
        " ".join([f"{idx + 1}）{_normalize_text(item)}" for idx, item in enumerate(guidance[:3]) if _normalize_text(item)]),
        220,
    )

    competition_advice = "答辩展示时，优先讲清项目价值、目标用户、证据来源和落地路径，避免只讲技术名词而弱化商业与评审价值。"
    if hg_conclusion:
        competition_advice = f"{competition_advice} 辅助判断上，超图侧也提示：{hg_conclusion}"

    lines = ["## 补充分析评审要点"]
    lines.append(f"- **总体评价：** {overall or '项目已有一定基础，但当前材料的说服力和完整度仍需继续增强。'}")
    lines.append(f"- **核心问题：** {core_problem}")
    lines.append(f"- **改进方向：** {direction or '优先补齐关键证据与缺失模块，再完善整体表达。'}")
    lines.append(f"- **大赛适配性建议：** {competition_advice}")
    return "\n".join(lines)


def _review_summary_markdown(
    text: str,
    audience_role: str,
    dimension_scores: list[dict[str, Any]],
    missing_parts: list[dict[str, str]],
    logic_result: dict[str, Any],
    issues: list[dict[str, Any]],
    hypergraph_context: dict[str, Any] | None = None,
) -> str:
    del audience_role, dimension_scores, logic_result
    coverage = _section_coverage(text)
    strengths = _build_strengths(text, coverage, hypergraph_context=hypergraph_context)
    return _compose_summary(strengths, issues, missing_parts, hypergraph_context=hypergraph_context)


def _default_mermaid_canvas_code() -> str:
    return (
        "flowchart LR\n"
        "CS[客户细分] --> VP[价值主张]\n"
        "VP --> CH[渠道通路]\n"
        "VP --> CR[客户关系]\n"
        "VP --> RS[收入来源]\n"
        "KR[关键资源] --> VP\n"
        "KA[关键活动] --> VP\n"
        "KP[关键合作] --> VP\n"
        "CO[成本结构] --> RS"
    )


def _mermaid_canvas_rules() -> str:
    return (
        "Mermaid 画布规则（必须严格遵守）：\n"
        "1) 只输出一个 ```mermaid 代码块，禁止输出解释文字；\n"
        "2) 第一行必须是 flowchart LR；\n"
        "3) 仅允许 9 个节点 ID：CS、VP、CH、CR、RS、KR、KA、KP、CO；\n"
        "4) 节点标签用短语，建议 4-8 个字，避免长句；\n"
        "5) 仅允许 --> 连线，边数控制在 8-12；\n"
        "6) 禁止 subgraph、style、classDef、linkStyle、click、HTML 标签、注释。"
    )


def _build_mermaid_canvas_prompt(project_text: str) -> str:
    return (
        "请根据以下项目文本生成“简洁、统一、可展示”的商业模式画布 Mermaid。\n"
        f"{_mermaid_canvas_rules()}\n"
        "参考结构（可替换节点标签，但必须保持同一结构）：\n"
        "flowchart LR\n"
        "CS[客户细分] --> VP[价值主张]\n"
        "VP --> CH[渠道通路]\n"
        "VP --> CR[客户关系]\n"
        "VP --> RS[收入来源]\n"
        "KR[关键资源] --> VP\n"
        "KA[关键活动] --> VP\n"
        "KP[关键合作] --> VP\n"
        "CO[成本结构] --> RS\n"
        f"项目文本：{_normalize_text(project_text)[:2600]}"
    )


def _normalize_mermaid_sections(markdown_text: str) -> str:
    text = str(markdown_text or "")
    if not text:
        return text
    pattern = re.compile(r"```mermaid\s*([\s\S]*?)```", flags=re.IGNORECASE)
    return pattern.sub(lambda m: _normalize_mermaid_block(m.group(1)), text)


def _normalize_mermaid_block(raw: str) -> str:
    text = str(raw or "").strip()
    fallback_code = _default_mermaid_canvas_code()
    if not text:
        return f"```mermaid\n{fallback_code}\n```"

    mermaid_fenced = re.search(r"```mermaid\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    fenced = re.search(r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)\s*```", text)
    code = (mermaid_fenced or fenced).group(1).strip() if (mermaid_fenced or fenced) else text
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    code_lines = [line.strip() for line in code.split("\n") if line.strip()]

    if not code_lines:
        return f"```mermaid\n{fallback_code}\n```"

    merged_lower = "\n".join(code_lines).lower()
    forbidden_tokens = ("subgraph", "classdef", "linkstyle", "style ", " click ", ":::", "<br", "%%")
    relation_lines = [line for line in code_lines if "-->" in line]

    if any(token in merged_lower for token in forbidden_tokens):
        code = fallback_code
    elif len(code_lines) > 20 or len(relation_lines) < 6 or len(relation_lines) > 14:
        code = fallback_code
    else:
        if re.match(r"^(graph|flowchart)\b", code_lines[0], flags=re.IGNORECASE):
            code_lines = code_lines[1:]
        code = "flowchart LR\n" + "\n".join(code_lines[:14])

    if not re.search(r"\bCS\[", code) or not re.search(r"\bVP\[", code):
        code = fallback_code

    return f"```mermaid\n{code}\n```"


def diagnose_pdf(
    pages: list[dict[str, Any]],
    audience_role: str,
    hypergraph_context: dict[str, Any] | None = None,
    project_type: str = "auto",
) -> dict[str, Any]:
    full_text = "\n".join(str((page or {}).get("text", "") or "") for page in (pages or [])).strip()
    normalized_project_type = _normalize_project_type(project_type, full_text)
    material_state = _project_material_state(full_text)
    completeness = _detect_completeness(full_text)
    case_patterns = _load_case_patterns(limit=3)
    scene_key = "student_pdf_review" if audience_role == "student" else "teacher_scoring"
    base_scene_prompt = _load_scene_prompt(scene_key, "default", case_patterns)
    role_system_prompt = TEACHER_REVIEW_PROMPT if audience_role == "teacher" else GUIDE_SYSTEM_PROMPT

    if not material_state.get("related"):
        return {
            "issues": [
                {
                    "dimension": "完整性",
                    "description": "当前上传内容与创新创业项目计划书的关联较弱，无法形成有效检阅。",
                    "question": "你能否先补充项目摘要，并说清目标用户、痛点、方案和验证方式？",
                    "risk_level": "high",
                    "evidence": "文本未形成清晰的项目结构，无法识别基本评审主线。",
                }
            ],
            "annotations": [],
            "guidance_questions": ["如果要先补一段项目摘要，你会如何说清用户、痛点、方案和验证方式？"],
            "examples": ["示例：项目摘要至少要写清目标用户、问题、解决方案和验证方式。"],
            "suggestions": [OFF_TOPIC_HINT],
            "summary": "当前上传内容与创新创业项目相关性较弱，暂时无法按完整项目计划书检阅。请重新上传包含目标用户、痛点、方案、验证和商业模式的项目材料。",
            "review_meta": {
                "unrelated_content": True,
                "project_type": normalized_project_type,
                "dimension_scores": [],
                "is_complete": False,
                "progress": 10,
                "missing_parts": [{"part": "项目基本主线", "urgency": "high"}],
                "project_material_state": "unrelated",
                "is_partial_project": False,
                "case_patterns": case_patterns,
                "hypergraph": _compact_hypergraph_context(hypergraph_context),
            },
            "dimension_scores": [],
            "total_score": 0,
            "score_max": 100,
            "case_patterns": case_patterns,
            "policy": PROMPT_POLICY.get(audience_role, PROMPT_POLICY["student"]),
            "system_prompt": role_system_prompt,
            "pdf_prompt": PDF_REVIEW_PROMPT,
            "special_scene": "unrelated_content",
            "scene_prompt": base_scene_prompt,
        }

    if not completeness.get("is_complete"):
        missing_parts = list(completeness.get("missing_parts") or [])
        progress = int(completeness.get("progress") or 0)
        guidance_questions = [
            f"请先补齐 {item.get('part', '关键部分')}（紧急程度：{item.get('urgency', 'medium')}）"
            for item in missing_parts[:5]
        ]
        incomplete_summary = _llm_incomplete_feedback(
            full_text,
            progress,
            missing_parts,
            audience_role=audience_role,
        )
        suggestions = [
            "优先补齐高紧急程度部分，再完善中低紧急度模块。",
            "补齐后再发起一键检阅，可获得更完整的批注和评分结果。",
            "公益项目建议补充社会影响评估；商业项目建议补充收入与现金流假设。"
            if normalized_project_type == "public_welfare"
            else "商业项目建议优先补齐TAM/SAM/SOM、定价依据与单位经济模型。",
        ]
        return {
            "issues": [
                {
                    "dimension": "完整性",
                    "description": "项目当前仍处于部分完成状态，建议先补齐核心模块。",
                    "question": "你准备先补哪一部分？",
                    "risk_level": "medium",
                    "evidence": f"当前识别到 {len(missing_parts)} 个关键模块仍未补齐。",
                }
            ],
            "annotations": [],
            "guidance_questions": guidance_questions,
            "examples": [],
            "suggestions": suggestions,
            "summary": incomplete_summary,
            "review_meta": {
                "is_complete": False,
                "progress": progress,
                "missing_parts": missing_parts,
                "project_type": normalized_project_type,
                "dimension_scores": [],
                "total_score": 0,
                "score_max": 100,
                "project_material_state": "partial_project",
                "is_partial_project": True,
                "case_patterns": case_patterns,
                "hypergraph": _compact_hypergraph_context(hypergraph_context),
            },
            "dimension_scores": [],
            "total_score": 0,
            "score_max": 100,
            "case_patterns": case_patterns,
            "policy": PROMPT_POLICY.get(audience_role, PROMPT_POLICY["student"]),
            "system_prompt": role_system_prompt,
            "pdf_prompt": PDF_REVIEW_PROMPT,
            "special_scene": "incomplete_project",
            "scene_prompt": base_scene_prompt,
        }

    missing_parts = _compute_missing_parts(full_text)
    logic_result = validate_logic(full_text)
    legacy_dimension_scores = _build_dimension_scores(full_text, hypergraph_context=hypergraph_context)
    rubric_result = rubric_agent_score(
        full_text,
        hypergraph_context=hypergraph_context,
        project_type=normalized_project_type,
    )
    rubric_dimension_scores = (rubric_result or {}).get("dimensions") or _build_rubric_fallback_scores(
        full_text,
        hypergraph_context=hypergraph_context,
    ).get("dimensions") or []
    fallback_issues = _build_issues(
        full_text,
        missing_parts,
        logic_result,
        legacy_dimension_scores,
        hypergraph_context=hypergraph_context,
    )
    fallback_summary = _review_summary_markdown(
        full_text,
        audience_role,
        legacy_dimension_scores,
        missing_parts,
        logic_result,
        fallback_issues,
        hypergraph_context=hypergraph_context,
    )
    llm_payload = _llm_review_payload(
        pages=pages,
        audience_role=audience_role,
        hypergraph_context=hypergraph_context,
        project_type=normalized_project_type,
        missing_parts=missing_parts,
        logic_result=logic_result,
        fallback_scores=legacy_dimension_scores,
        fallback_summary=fallback_summary,
        material_state=material_state,
    )

    dimension_scores = rubric_dimension_scores
    issues = (llm_payload or {}).get("issues") or fallback_issues
    annotation_basis = (llm_payload or {}).get("annotations") or issues
    annotations = _build_annotations(pages, annotation_basis)
    guidance_questions = _dedupe_text_list(
        list((llm_payload or {}).get("guidance_questions") or [])
        + [item.get("question", "") for item in issues[:6] if _normalize_text(item.get("question"))],
        limit=8,
    )

    examples = (llm_payload or {}).get("examples") or _build_examples(missing_parts, issues)

    suggestions = []
    for item in logic_result.get("suggestions") or []:
        normalized = _normalize_text(item)
        if normalized and normalized not in suggestions:
            suggestions.append(normalized)
    for item in (llm_payload or {}).get("suggestions") or []:
        normalized = _normalize_text(item)
        if normalized and normalized not in suggestions:
            suggestions.append(normalized)
    if normalized_project_type == "public_welfare":
        welfare_suggestion = "请补充公益价值证据：受益对象规模、影响指标与可持续运营机制。"
        if welfare_suggestion not in suggestions:
            suggestions.append(welfare_suggestion)
    else:
        commercial_suggestion = "请补充商业化证据：TAM/SAM/SOM口径、定价依据与现金流测算。"
        if commercial_suggestion not in suggestions:
            suggestions.append(commercial_suggestion)

    if audience_role == "teacher":
        llm_suggestions = _call_llm(
            "请基于以下创业计划文本输出2条教师可编辑建议，每条不超过40字：\n" + (full_text[:1800] or ""),
            timeout_seconds=60,
            system_prompt=TEACHER_SYSTEM_PROMPT,
        )
        if llm_suggestions:
            suggestion_lines = [
                line.strip("- 1234567890.\t")
                for line in str(llm_suggestions).splitlines()
                if line.strip()
            ]
            suggestion_lines = [line for line in suggestion_lines if 6 <= len(line) <= 80]
            if suggestion_lines:
                suggestions = _dedupe_text_list(suggestion_lines, limit=2)

    progress = 100
    weighted_total = float((rubric_result or {}).get("total_score") or 0)
    if weighted_total <= 0:
        weighted_total = round(sum(float(item.get("weighted_score") or 0) for item in dimension_scores), 2)
    score_max = float((rubric_result or {}).get("max_score") or 0)
    if score_max <= 0:
        score_max = round(sum(float(item.get("weight") or 0) for item in dimension_scores), 2) or 5.0
    average_score = round(sum(float(item.get("score") or 0) for item in dimension_scores) / max(len(dimension_scores), 1), 2)
    if len(full_text.strip()) < 220:
        special_scene = "too_short"
    elif len(issues) <= 1:
        special_scene = "no_obvious_issue"
    elif len(issues) >= 4:
        special_scene = "severe_conflict"
    else:
        special_scene = "default"
    scene_prompt = _load_scene_prompt(
        scene_key,
        special_scene if scene_key == "student_pdf_review" else "default",
        case_patterns,
    )
    review_meta = {
        "project_type": normalized_project_type,
        "dimension_scores": dimension_scores,
        "is_complete": True,
        "progress": int(progress),
        "missing_parts": missing_parts,
        "average_score": average_score,
        "weighted_total_score": weighted_total,
        "total_score": weighted_total,
        "score_max": score_max or 5.0,
        "section_coverage": _section_coverage(full_text),
        "review_framework": "student_plan_review_v3",
        "review_engine": "llm_first" if llm_payload else "heuristic_fallback",
        "llm_used": bool(llm_payload),
        "rubric_engine": "llm_rubric_agent",
        "rubric_overall_summary": _normalize_text((rubric_result or {}).get("overall_summary")),
        "project_material_state": "document",
        "is_partial_project": False,
        "case_patterns": case_patterns,
        "hypergraph": _compact_hypergraph_context(hypergraph_context),
    }
    summary = (llm_payload or {}).get("summary") or fallback_summary
    if audience_role == "teacher":
        canvas_prompt = _build_mermaid_canvas_prompt(full_text)
        canvas_mermaid = _normalize_mermaid_block(
            _call_llm(canvas_prompt, timeout_seconds=60, system_prompt=TEACHER_SYSTEM_PROMPT)
        )
        summary = (
            "### 商业模式画布（Mermaid）\n"
            f"{canvas_mermaid}\n\n"
            "### 项目细节解读\n"
            "- 请重点核查价值主张是否与目标用户痛点一一对应。\n"
            "- 建议课堂先讲“证据链”，再讲“商业化闭环”。\n"
            "- 下方问题清单与建议可直接用于批改与教学。\n\n"
            "### 教师批阅结论\n"
            f"{summary}"
        )

    return {
        "issues": issues,
        "annotations": annotations,
        "guidance_questions": guidance_questions,
        "examples": examples,
        "suggestions": suggestions,
        "summary": summary,
        "review_meta": review_meta,
        "dimension_scores": dimension_scores,
        "total_score": weighted_total,
        "score_max": score_max or 5.0,
        "case_patterns": case_patterns,
        "policy": PROMPT_POLICY.get(audience_role, PROMPT_POLICY["student"]),
        "system_prompt": role_system_prompt,
        "pdf_prompt": PDF_REVIEW_PROMPT,
        "special_scene": special_scene,
        "scene_prompt": scene_prompt,
    }


def _infer_guidance_variant(stage: str, answer: str) -> str:
    text = _normalize_text(answer).lower()
    if _contains_any(text, ["不知道", "没想法", "迷茫", "不会", "不清楚"]):
        return "unknown_direction"
    if _contains_any(text, ["怎么做", "步骤", "流程", "如何写", "从哪里开始"]):
        return "need_step_help"
    if _contains_any(text, ["已经", "草稿", "初步", "目前", "我们做了"]):
        return "has_draft"
    if _contains_any(text, ["评委", "比赛", "评分", "答辩", "竞赛"]):
        return "match_competition"
    return "default"


def _build_guidance_chat_title(answer: str, teacher_reply: str) -> str:
    def _clean_title(text: str) -> str:
        normalized = re.sub(r"[\s\-—_,，。.!！?？:：;；/\\|]+", "", _normalize_text(text))
        return normalized[:15]

    candidate = _clean_title(answer)
    if candidate:
        return candidate
    candidate = _clean_title(teacher_reply)
    if candidate:
        return candidate
    return "项目引导"


def _compose_student_guidance_reply(
    current_stage: str,
    next_stage: str,
    answer: str,
    case_patterns: list[dict[str, str]],
    variant: str,
) -> str:
    fallback_question = STAGE_QUESTIONS.get(next_stage, STAGE_QUESTIONS["plan"])
    scene_prompt = _load_scene_prompt("student_chat", variant, case_patterns)
    case_text = _render_case_patterns(case_patterns)
    prompt = (
        "你是创新创业项目指导老师。"
        "请按学生所处阶段灵活回答，不固定模板，但必须包含："
        "先讲解原理，再给类比/示例，最后用问题引导。\n"
        "关键要求：\n"
        "1) 初学者语气更通俗、步骤更细；有草稿时语气更专业、强调证据链；\n"
        "2) 允许给方法、框架、步骤、计算口径示例（如成本估算思路），但不能直接代写完整项目；\n"
        "3) 若学生偏题，先简短回应，再引导回创新项目主线；\n"
        "4) 如果学生还没有明确项目，先帮助他从兴趣领域、熟悉场景、用户问题、可验证痛点中找到起步方向；\n"
        "5) 输出尽量让学生“下一步可执行”。\n"
        f"学生输入: {answer[:1200]}\n"
        f"场景变体: {variant}\n"
        f"参考案例范式:\n{case_text}\n"
        f"兜底引导问题: {fallback_question}\n"
        f"当前阶段：{current_stage}\n"
        f"下一阶段：{next_stage}\n"
        f"场景提示：{scene_prompt}"
    )
    content = _call_llm(prompt, timeout_seconds=60, system_prompt=GUIDE_SYSTEM_PROMPT)
    if content and _normalize_text(content):
        return content.strip()

    case_line = ""
    if case_patterns:
        first_case = case_patterns[0]
        case_line = (
            f"可以先参考 {first_case.get('industry', '同类项目')} 的常见做法："
            f"{first_case.get('logic') or first_case.get('innovation') or '先把问题、用户和方案对应起来。'}"
        )
    return (
        f"你现在已经走到“{current_stage}”这一步，下一步更关键的是把“{next_stage}”讲清楚。"
        f"先不要急着把内容写得很大，先把最核心的一步做实。\n"
        f"建议你优先回答：{fallback_question}\n"
        f"{KNOWLEDGE_HINTS.get(next_stage, '')}\n"
        f"{case_line}".strip()
    )


def next_guiding_question(stage: str, answer: str) -> dict[str, Any]:
    current = stage if stage in STAGE_FLOW else "idea"
    case_patterns = _load_case_patterns(limit=2)
    variant = _infer_guidance_variant(current, answer)
    scene_prompt = _load_scene_prompt("student_chat", variant, case_patterns)

    next_stage = STAGE_FLOW.get(current, current)
    teacher_reply = _compose_student_guidance_reply(current, next_stage, answer, case_patterns, variant)
    return {
        "stage": next_stage,
        "question": STAGE_QUESTIONS.get(next_stage, STAGE_QUESTIONS["plan"]),
        "teacher_reply": teacher_reply,
        "chat_title": _build_guidance_chat_title(answer, teacher_reply),
        "knowledge": KNOWLEDGE_HINTS.get(next_stage, ""),
        "example": "尽量给出具体用户、场景、证据或数据，不要只写口号。",
        "case_pattern": case_patterns[0] if case_patterns else {},
        "scene_prompt": scene_prompt,
        "question_type": "guided",
        "system_prompt": GUIDE_SYSTEM_PROMPT,
    }

def _classify_issue_label(text: str) -> str:
    content = str(text or "")
    for label, keywords in COMMON_ISSUE_RULES:
        if _contains_any(content, keywords):
            return label
    return "核心论证仍需加强"


def summarize_common_issues(review_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter()
    sample_case: dict[str, str] = {}
    for record in review_records or []:
        for issue in record.get("issues", []) or []:
            description = _normalize_text((issue or {}).get("description") or issue)
            if not description:
                continue
            label = _classify_issue_label(description)
            counter[label] += 1
            sample_case.setdefault(label, description)
    return [
        {"problem_type": label, "frequency": count, "sample_case": sample_case.get(label, "")}
        for label, count in counter.most_common(6)
    ]


def summarize_common_issues_from_review_outputs(review_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in review_payloads or []:
        normalized.append({"issues": item.get("issues") or []})
    return summarize_common_issues(normalized)


def summarize_common_issues_from_plan_texts(review_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed = []
    for item in review_payloads or []:
        text = _normalize_text(item.get("text") or "")
        if not text:
            continue
        payload = diagnose_pdf([{"page": 1, "text": text}], "teacher")
        parsed.append({"issues": payload.get("issues") or []})
    return summarize_common_issues(parsed)


def recommend_knowledge(common_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    template_bank = [
        {
            "match": ["问题", "场景", "痛点", "定义", "聚焦"],
            "knowledge_point": "问题定义与场景收敛",
            "teaching_goal": "让学生用“谁在什么场景下遇到什么可验证问题”一句话讲清核心问题。",
            "core_concepts": ["问题陈述句", "场景边界", "优先级判断"],
            "teaching_path": ["先写现象", "再写受影响用户", "最后写损失与紧迫性"],
            "class_activity": "给出3个泛化问题描述，要求学生改写为可验证场景句并互评。",
            "after_class_task": "提交1页“问题定义卡”：问题句、目标用户、场景截图/访谈证据各1条。",
            "assessment_rubric": "问题是否具体、场景是否可复现、证据是否可追溯。",
            "teacher_prompt": "如果删掉“创新”“平台”等大词，你的问题句还能成立吗？",
        },
        {
            "match": ["用户", "访谈", "问卷", "样本", "调研", "证据"],
            "knowledge_point": "用户研究与证据链设计",
            "teaching_goal": "让学生能用样本结构、访谈证据和数据口径支撑关键判断。",
            "core_concepts": ["样本代表性", "证据分级", "口径一致性"],
            "teaching_path": ["先定义样本", "再展示证据", "最后给出结论边界"],
            "class_activity": "分组审查一份访谈纪要，标注“事实-推断-结论”三层证据。",
            "after_class_task": "补交访谈/问卷摘要：样本量、关键原话、结论和局限各1项。",
            "assessment_rubric": "样本是否匹配目标用户、结论是否由证据直接支持。",
            "teacher_prompt": "你的这个结论对应哪条原始证据？如果没有，这条结论先降级。",
        },
        {
            "match": ["方案", "价值", "差异", "可行性", "技术"],
            "knowledge_point": "方案论证与价值主张表达",
            "teaching_goal": "让学生把“问题-方案-效果”讲成闭环，并说清与替代方案的差异。",
            "core_concepts": ["价值主张", "功能到价值映射", "MVP验证路径"],
            "teaching_path": ["定义目标效果", "映射关键功能", "补充验证计划"],
            "class_activity": "让学生用“我们通过X为Y用户减少/提升Z”格式改写方案介绍。",
            "after_class_task": "提交方案对照表：现有替代方案、你的方案、差异指标各3条。",
            "assessment_rubric": "是否对齐痛点、是否可验证、是否有差异化指标。",
            "teacher_prompt": "你的方案比现有做法好在哪里？请用一个可量化指标回答。",
        },
        {
            "match": ["商业", "盈利", "收入", "成本", "获客", "渠道"],
            "knowledge_point": "商业模式与经营闭环",
            "teaching_goal": "让学生能完整说明客户、价值、收入、成本和获客路径的闭环关系。",
            "core_concepts": ["收入模型", "成本结构", "单位经济", "渠道转化漏斗"],
            "teaching_path": ["先定客户与付费意愿", "再算收入与成本", "最后验证获客效率"],
            "class_activity": "课堂推演一轮“单客经济模型”：客单价、毛利、回本周期。",
            "after_class_task": "提交简版财务测算表：收入假设、成本项、敏感性参数。",
            "assessment_rubric": "假设是否透明、口径是否一致、回本逻辑是否成立。",
            "teacher_prompt": "如果获客成本上升30%，你的模型是否仍能回本？",
        },
        {
            "match": ["财务", "现金流", "预算", "回本", "毛利", "利润"],
            "knowledge_point": "财务测算与关键假设管理",
            "teaching_goal": "让学生用清晰假设完成收入、成本、现金流的基础测算。",
            "core_concepts": ["关键假设", "敏感性分析", "现金流安全边际"],
            "teaching_path": ["列假设", "做测算", "做压力测试"],
            "class_activity": "选择一个项目做“最佳/基准/保守”三情景测算对比。",
            "after_class_task": "提交三情景测算截图，并写出导致波动最大的2个变量。",
            "assessment_rubric": "是否解释假设来源、是否展示风险场景、是否有应对方案。",
            "teacher_prompt": "你最脆弱的财务假设是什么？如果失效，Plan B 是什么？",
        },
        {
            "match": ["市场", "竞品", "tam", "sam", "som", "竞争"],
            "knowledge_point": "市场规模与竞品分析方法",
            "teaching_goal": "让学生基于市场边界和竞品对比证明切入机会与竞争策略。",
            "core_concepts": ["TAM/SAM/SOM", "竞品坐标", "切入点策略"],
            "teaching_path": ["先定边界", "再做竞品对比", "最后给切入策略"],
            "class_activity": "课堂共创竞品矩阵：价格、性能、场景覆盖、进入壁垒。",
            "after_class_task": "提交市场口径说明：数据来源、计算过程、关键结论。",
            "assessment_rubric": "边界是否清晰、数据是否可信、策略是否可执行。",
            "teacher_prompt": "为什么你的切入点不是头部竞品最强的那一段？",
        },
        {
            "match": ["实施", "里程碑", "执行", "团队", "分工", "计划"],
            "knowledge_point": "里程碑设计与执行管理",
            "teaching_goal": "让学生把目标拆成阶段里程碑，并明确负责人与验收标准。",
            "core_concepts": ["里程碑", "责任分工", "验收指标", "风险前置"],
            "teaching_path": ["拆目标", "定负责人", "设验收点与风险预案"],
            "class_activity": "把一个大目标拆成12周执行看板并现场过评审问答。",
            "after_class_task": "提交阶段计划：每周目标、负责人、产出物与风险应对。",
            "assessment_rubric": "任务是否可执行、责任是否清晰、验收标准是否量化。",
            "teacher_prompt": "这个里程碑完成后，你拿什么证据证明“真的完成了”？",
        },
        {
            "match": ["表达", "结构", "材料", "展示", "路演", "叙事"],
            "knowledge_point": "路演叙事与材料结构优化",
            "teaching_goal": "让学生在有限时间内完成“问题-方案-证据-商业化”高密度表达。",
            "core_concepts": ["叙事主线", "结论先行", "图表证据化"],
            "teaching_path": ["先给结论", "再给证据", "最后给行动计划"],
            "class_activity": "3分钟快讲演练：每人只保留3张核心页并接受追问。",
            "after_class_task": "提交精简版PPT（不超过8页）并标注每页结论句。",
            "assessment_rubric": "主线是否清晰、证据是否支撑结论、答辩是否抗压。",
            "teacher_prompt": "如果只留一句话让评委记住，你希望是哪一句？",
        },
    ]

    recommendations: list[dict[str, Any]] = []
    for item in common_issues or []:
        issue_text = _normalize_text(item.get("problem_type") or item.get("issue") or item.get("title") or "")
        if not issue_text:
            continue
        summary_text = _normalize_text(item.get("sample_case") or item.get("summary") or "")
        frequency = _safe_int(item.get("frequency") or item.get("count"), default=1)

        template = None
        for row in template_bank:
            if _contains_any(issue_text, row.get("match") or []):
                template = row
                break
        if template is None:
            template = {
                "knowledge_point": "项目论证结构与证据增强",
                "teaching_goal": "帮助学生把结论建立在证据链和逻辑链之上。",
                "core_concepts": ["论证链", "证据链", "结论边界"],
                "teaching_path": ["先找关键结论", "再找支撑证据", "最后补齐缺口"],
                "class_activity": "选取项目片段做“结论-依据”反向标注练习。",
                "after_class_task": "提交一版“结论-证据对照表”，每个结论至少对应一条证据。",
                "assessment_rubric": "结论是否可验证、证据是否足够、推理是否连贯。",
                "teacher_prompt": "这条结论的最小证据单元是什么？",
            }

        priority = "高" if frequency >= 5 else ("中" if frequency >= 3 else "低")
        recommended_minutes = 30 if priority == "高" else (20 if priority == "中" else 12)
        activity_text = str(template.get("class_activity") or "")
        if summary_text:
            activity_text = f"{activity_text} 可结合本班典型表现：{_truncate(summary_text, 120)}"

        recommendations.append(
            {
                "issue": issue_text,
                "knowledge_point": str(template.get("knowledge_point") or "项目论证结构与证据增强"),
                "teaching_goal": str(template.get("teaching_goal") or ""),
                "core_concepts": _safe_list(template.get("core_concepts")),
                "teaching_path": _safe_list(template.get("teaching_path")),
                "class_activity": activity_text,
                "after_class_task": str(template.get("after_class_task") or ""),
                "assessment_rubric": str(template.get("assessment_rubric") or ""),
                "teacher_prompt": str(template.get("teacher_prompt") or ""),
                "priority": priority,
                "recommended_minutes": recommended_minutes,
                "source_frequency": max(1, frequency),
            }
        )

    if recommendations:
        return recommendations[:6]

    return [
        {
            "issue": "共性问题待补充",
            "knowledge_point": "项目论证结构与证据增强",
            "teaching_goal": "帮助学生补齐问题定义、证据与商业闭环。",
            "core_concepts": ["问题定义", "证据设计", "商业闭环"],
            "teaching_path": ["定位问题", "补证据", "再校验商业逻辑"],
            "class_activity": "课堂快速诊断：逐项检查问题、证据、方案、商业模式是否闭环。",
            "after_class_task": "每个项目提交一页“本周补证据计划”。",
            "assessment_rubric": "是否形成问题-证据-方案闭环。",
            "teacher_prompt": "你当前最缺的一条证据是什么？",
            "priority": "中",
            "recommended_minutes": 20,
            "source_frequency": 1,
        }
    ]


def _build_student_chat_fallback(question: str, context: dict[str, Any]) -> str:
    review = context.get("review") or {}
    issues = review.get("issues") or context.get("issues") or []
    top_issue = (issues[0] or {}) if issues else {}
    summary = _normalize_text(review.get("summary") or context.get("summary") or "")
    return (
        "## 先解释\n"
        f"你现在追问的是：{_normalize_text(question)}。系统主要是根据文档主线、证据完整度和评审维度做出的判断。"
        f"{(' 当前最需要优先处理的问题是：' + _normalize_text(top_issue.get('description'))) if _normalize_text(top_issue.get('description')) else ''}\n"
        "## 举例说明\n"
        f"{summary or '系统会优先检查创新点、逻辑框架、可行性、完整性和大赛适配这五个维度。'}\n"
        "## 建议你思考\n"
        f"{_normalize_text(top_issue.get('question')) or '如果评委现在追问这一点，你最缺哪一条证据来回答？'}"
    )


def student_pdf_chat_answer(question: str, context: dict[str, Any]) -> str:
    plan_excerpt = _normalize_text(context.get("plan_excerpt") or context.get("text") or "")
    material_state = _project_material_state(plan_excerpt + "\n" + question)
    if not material_state.get("related"):
        return "你提供的内容与项目计划书关联较弱。请先上传项目方案，或先说明目标用户、痛点、方案和验证方式。"

    case_patterns = _load_case_patterns(limit=2)
    scene_prompt = _load_scene_prompt("student_pdf_review", "default", case_patterns)
    hypergraph_block = _render_hypergraph_prompt_block(context.get("hypergraph") or context.get("hypergraph_context"))
    review_snapshot = {
        "summary": context.get("summary") or (context.get("review") or {}).get("summary"),
        "issues": (context.get("issues") or (context.get("review") or {}).get("issues") or [])[:5],
        "guidance_questions": (context.get("guidance_questions") or (context.get("review") or {}).get("guidance_questions") or [])[:5],
    }
    prompt = (
        "你是负责细致的一对一创新教导员。请基于学生整份项目书和检阅结果回答。\n"
        "建议使用 Markdown，优先做到“先解释判断依据、再给例子、最后给下一步思考”，但不强制固定标题。\n"
        "要求：不能直接代写整份项目书；可以给方法、示例、判断依据。"
        "如果学生问的是错别字或语病，请给改写建议；"
        "如果学生问的是逻辑、可行性、财务或风险，请说明评审视角与修订路径。\n"
        f"学生问题：{_normalize_text(question)}\n"
        f"评审上下文：{json.dumps(review_snapshot, ensure_ascii=False)[:2600]}\n"
        f"{hypergraph_block}"
        f"场景提示：{scene_prompt}"
    )
    llm_result = _call_llm(prompt, timeout_seconds=LLM_REVIEW_TIMEOUT_SECONDS, system_prompt=PDF_REVIEW_SYSTEM_PROMPT)
    if llm_result:
        return llm_result.strip()
    return _build_student_chat_fallback(question, context)


def _build_teacher_chat_fallback(question: str, context: dict[str, Any]) -> str:
    review = context.get("review") or {}
    issues = review.get("issues") or []
    top_issue = (issues[0] or {}) if issues else {}
    hypergraph = _compact_hypergraph_context(
        context.get("hypergraph") or context.get("hypergraph_context") or (review.get("review_meta") or {}).get("hypergraph")
    )
    hg_conclusion = _stringify_value((hypergraph.get("diagnosis_summary") or {}).get("conclusion"))
    canvas_block = _normalize_mermaid_block("")
    return (
        "### 商业模式画布（Mermaid）\n"
        f"{canvas_block}\n\n"
        "## 问题分析\n"
        f"当前教师问题：{_normalize_text(question)}。项目当前最优先的问题是{_normalize_text(top_issue.get('description')) or '证据和结构仍需加强'}。\n"
        "## 讲解与批注建议\n"
        f"建议先向学生解释为什么会得到这个判断：{_normalize_text(top_issue.get('evidence')) or '因为方案主线和证据链还没有完全闭合。'}\n"
        f"{('超图辅助结论：' + hg_conclusion) if hg_conclusion else ''}\n"
        "## 教学建议\n"
        f"课堂上可追问：{_normalize_text(top_issue.get('question')) or '如果评委现在追问这一点，学生能拿出什么证据来回答？'}\n"
        "## 可直接对学生说的话\n"
        "你现在最需要补的不是更多描述，而是能直接支撑核心判断的证据和一条完整的论证链。"
    )


def teacher_chat_answer(question: str, context: dict[str, Any]) -> str:
    variant = "summary"
    context_type = context.get("type", "prep")
    if context_type == "review":
        variant = "single_student"
    elif _contains_any(question, ["课堂", "上课", "讲解", "备课", "教学"]):
        variant = "teach_topic"

    case_patterns = _load_case_patterns(limit=2)
    scene = "teacher_prep" if context_type == "prep" else "teacher_scoring"
    scene_prompt = _load_scene_prompt(scene, variant if scene == "teacher_prep" else "default", case_patterns)
    review = context.get("review") or {}
    review_meta = review.get("review_meta") or {}
    plan = context.get("plan") or {}
    hypergraph_context = context.get("hypergraph") or context.get("hypergraph_context") or review_meta.get("hypergraph")
    hypergraph_block = _render_hypergraph_prompt_block(
        hypergraph_context,
        title="以下是当前项目的超图诊断结果，请把它作为教师讲解和追问时的辅助证据：",
    )
    context_snapshot = {
        "type": context_type,
        "plan": {
            "id": plan.get("id"),
            "title": plan.get("title") or plan.get("name"),
            "student_name": plan.get("student_name") or plan.get("student"),
            "status": plan.get("status"),
        },
        "review": {
            "summary": review.get("summary"),
            "issues": (review.get("issues") or [])[:6],
            "guidance_questions": (review.get("guidance_questions") or [])[:6],
            "dimension_scores": (review.get("dimension_scores") or review_meta.get("dimension_scores") or [])[:6],
        },
        "history": (context.get("history") or [])[:4],
    }
    prompt = (
        "请按教师可直接使用的格式回答。\n"
        "不要求固定模板，但建议覆盖：问题分析、讲解与批注建议、教学建议、可直接对学生说的话。\n"
        "若上下文是项目检阅，可优先给商业模式画布 Mermaid 代码块再解释；如果文字建议更关键，也可直接给结论。\n"
        "Mermaid 部分必须简洁统一：第一行固定 flowchart LR，仅保留九个标准模块（客户细分、价值主张、渠道通路、客户关系、收入来源、关键资源、关键活动、关键合作、成本结构），"
        "不要 subgraph/style/classDef/linkStyle/click，不要长句节点。\n"
        "如果存在超图诊断，必须说明诊断出了什么、为什么会得到这个结果，以及建议学生补什么证据。\n"
        "不要复述 JSON 字段名，要把结论和证据说成人能直接理解的话。\n"
        f"教师提问：{_normalize_text(question)}\n"
        f"项目上下文：{json.dumps(context_snapshot, ensure_ascii=False)[:2600]}\n"
        f"{hypergraph_block}"
        f"场景提示：{scene_prompt}"
    )
    llm_result = _call_llm(prompt, timeout_seconds=LLM_REVIEW_TIMEOUT_SECONDS, system_prompt=TEACHER_SYSTEM_PROMPT)
    if llm_result:
        return _normalize_mermaid_sections(llm_result.strip())
    return _build_teacher_chat_fallback(question, context)

