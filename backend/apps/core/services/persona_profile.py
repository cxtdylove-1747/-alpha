from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import re
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from ..models import ConversationRecord, MentorshipRelation, Plan, ReviewRecord

User = get_user_model()


@dataclass(frozen=True)
class DimensionDef:
    key: str
    label: str
    summary_hint: str
    weakness_hint: str
    keywords: tuple[str, ...]


DIMENSIONS: tuple[DimensionDef, ...] = (
    DimensionDef(
        key="innovation",
        label="创新洞察",
        summary_hint="能够提出差异化价值点，并尝试把想法落到具体场景。",
        weakness_hint="创新点表达还不够尖锐，建议强化“为什么是你”与差异依据。",
        keywords=(
            "创新",
            "差异化",
            "壁垒",
            "首创",
            "独特",
            "替代方案",
            "护城河",
            "moat",
            "usp",
            "value proposition",
            "蓝海",
            "innovation",
            "differentiation",
        ),
    ),
    DimensionDef(
        key="evidence",
        label="证据意识",
        summary_hint="会主动寻找访谈、调研与数据证据来支撑主张。",
        weakness_hint="论据偏主观，建议补充访谈样本、对比数据与可追溯来源。",
        keywords=(
            "访谈",
            "问卷",
            "数据",
            "证据",
            "样本",
            "验证",
            "调研",
            "evidence",
            "interview",
            "survey",
            "quote",
            "behavioral data",
            "trace",
            "来源",
        ),
    ),
    DimensionDef(
        key="business",
        label="商业建模",
        summary_hint="具备基本商业化思维，能讨论收入、成本和增长路径。",
        weakness_hint="商业闭环仍偏粗糙，建议补齐付费对象、定价逻辑与盈利节奏。",
        keywords=(
            "商业模式",
            "盈利",
            "收入",
            "成本",
            "定价",
            "现金流",
            "ltv",
            "cac",
            "tam",
            "sam",
            "som",
            "unit economics",
            "payback",
            "bep",
            "pricing",
            "revenue",
            "cost",
        ),
    ),
    DimensionDef(
        key="execution",
        label="执行规划",
        summary_hint="能把目标拆成阶段任务，并关注里程碑推进。",
        weakness_hint="执行计划颗粒度不足，建议按周拆解里程碑并绑定责任人。",
        keywords=(
            "里程碑",
            "计划",
            "执行",
            "排期",
            "资源",
            "风险应对",
            "mvp",
            "roadmap",
            "timeline",
            "milestone",
            "resource match",
            "落地",
            "交付",
        ),
    ),
    DimensionDef(
        key="communication",
        label="表达协作",
        summary_hint="表达结构较清晰，能够围绕问题持续沟通和迭代。",
        weakness_hint="表达仍有跳跃，建议先结论后依据，并保留关键复盘记录。",
        keywords=(
            "路演",
            "表达",
            "叙事",
            "协作",
            "反馈",
            "复盘",
            "总结",
            "pitch",
            "pitch deck",
            "storytelling",
            "q&a",
            "答辩",
            "presentation",
        ),
    ),
    DimensionDef(
        key="learning",
        label="学习迭代",
        summary_hint="具备较好的学习迁移能力，能够将反馈转成下一步动作。",
        weakness_hint="学习闭环不稳定，建议每轮固定产出“问题-证据-动作”记录。",
        keywords=(
            "学习",
            "改进",
            "迭代",
            "反思",
            "练习",
            "自检",
            "next task",
            "action item",
            "反馈",
            "iteration",
            "practice",
            "coach",
        ),
    ),
)


def _clip(text: str, limit: int = 220) -> str:
    return str(text or "").strip().replace("\n", " ")[:limit]


def _text_contains_any(text: str, keywords: tuple[str, ...]) -> list[str]:
    raw = str(text or "").lower()
    compact = re.sub(r"[\s/_\-]+", "", raw)
    hits: list[str] = []
    for kw in keywords:
        key = str(kw or "").strip().lower()
        if not key:
            continue
        compact_key = re.sub(r"[\s/_\-]+", "", key)
        if key in raw or (compact_key and compact_key in compact):
            hits.append(kw)
    return hits


SOURCE_QUALITY_WEIGHT: dict[str, float] = {
    "chat": 0.9,
    "plan": 1.2,
    "review": 1.55,
}


def _recentness_weight(created_at) -> float:
    if not created_at:
        return 0.88
    try:
        delta_days = max(0.0, (timezone.now() - created_at).total_seconds() / 86400.0)
    except Exception:
        return 0.88
    if delta_days <= 14:
        return 1.12
    if delta_days <= 60:
        return 1.0
    if delta_days <= 180:
        return 0.9
    return 0.82


def _row_timestamp(value) -> float:
    if not value:
        return 0.0
    try:
        return float(value.timestamp())
    except Exception:
        return 0.0


def _clean_text_fragment(text: Any, limit: int = 280) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    # Remove code blocks and markdown symbols to keep evidence snippets readable.
    raw = re.sub(r"```[\s\S]*?```", " ", raw)
    raw = re.sub(r"`[^`]*`", " ", raw)
    raw = re.sub(r"^#{1,6}\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"[\t\r\n]+", " ", raw)
    raw = re.sub(r"\s{2,}", " ", raw).strip()
    return raw[:limit]


def _collect_review_segments(review: ReviewRecord) -> list[str]:
    segments: list[str] = []
    for issue in (review.issues or []):
        if not isinstance(issue, dict):
            continue
        segments.extend(
            [
                issue.get("description"),
                issue.get("question"),
                issue.get("evidence"),
                issue.get("snippet"),
            ]
        )
    segments.extend(list(review.guidance_questions or []))
    segments.extend(list(review.suggestions or []))
    segments.extend(list(review.examples or []))

    review_meta = review.review_meta if isinstance(review.review_meta, dict) else {}
    for row in (review_meta.get("dimension_scores") or []):
        if not isinstance(row, dict):
            continue
        segments.extend(
            [
                row.get("label"),
                row.get("reason"),
                row.get("comment"),
                row.get("suggestion"),
            ]
        )

    if review.summary:
        segments.append(review.summary)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in segments:
        cleaned = _clean_text_fragment(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
        if len(deduped) >= 48:
            break
    return deduped


def _match_score_for_row(row: dict[str, Any], matched_keywords: list[str], total_keywords: int) -> float:
    source_type = str(row.get("source_type") or "")
    source_weight = SOURCE_QUALITY_WEIGHT.get(source_type, 0.9)
    coverage = len(matched_keywords) / max(total_keywords, 1)
    text_length = len(str(row.get("text") or ""))
    text_bonus = min(0.28, math.log1p(max(0, text_length)) * 0.035)
    score = 0.52 + source_weight + (coverage * 1.05) + _recentness_weight(row.get("created_at")) + text_bonus
    return round(score, 4)


def _score_from_hits(hits: list[dict[str, Any]], keyword_size: int) -> float:
    if not hits:
        return 1.2

    total_match_score = sum(float(item.get("match_score") or 0.0) for item in hits)
    unique_keywords: set[str] = set()
    source_types: set[str] = set()
    for item in hits:
        source_types.add(str(item.get("source_type") or ""))
        for kw in item.get("keywords") or []:
            if str(kw).strip():
                unique_keywords.add(str(kw).strip().lower())

    coverage_ratio = len(unique_keywords) / max(keyword_size, 1)
    source_diversity = len([x for x in source_types if x]) / max(len(SOURCE_QUALITY_WEIGHT), 1)
    strong_hits = sum(1 for item in hits if float(item.get("match_score") or 0.0) >= 2.5)

    score = 1.12
    score += min(2.05, math.log1p(total_match_score) * 1.08)
    score += coverage_ratio * 0.96
    score += source_diversity * 0.7
    score += min(0.58, strong_hits * 0.1)
    return round(max(1.0, min(5.0, score)), 2)


def _pick_balanced_hits(hits: list[dict[str, Any]], limit_per_dimension: int) -> list[dict[str, Any]]:
    if len(hits) <= limit_per_dimension:
        return hits

    source_caps = {
        "review": max(3, limit_per_dimension // 3 + 1),
        "plan": max(2, limit_per_dimension // 3),
        "chat": max(2, limit_per_dimension // 3),
    }
    picked: list[dict[str, Any]] = []
    picked_ids: set[tuple[Any, Any]] = set()

    for source_type in ("review", "plan", "chat"):
        rows = [item for item in hits if str(item.get("source_type") or "") == source_type]
        for row in rows[: source_caps.get(source_type, limit_per_dimension)]:
            row_id = (row.get("source_type"), row.get("source_id"))
            if row_id in picked_ids:
                continue
            picked_ids.add(row_id)
            picked.append(row)
            if len(picked) >= limit_per_dimension:
                return picked

    for row in hits:
        row_id = (row.get("source_type"), row.get("source_id"))
        if row_id in picked_ids:
            continue
        picked.append(row)
        picked_ids.add(row_id)
        if len(picked) >= limit_per_dimension:
            break
    return picked


def _collect_student_artifacts(user: User, max_rows: int = 160) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    chats = (
        ConversationRecord.objects.filter(user=user)
        .exclude(stage="review_task")
        .order_by("-created_at")[: max_rows]
    )
    for item in chats:
        content = f"{item.question or ''}\n{item.answer or ''}".strip()
        if not content:
            continue
        rows.append(
            {
                "source_type": "chat",
                "source_id": item.id,
                "title": f"对话 · {item.stage or 'chat'}",
                "text": content,
                "created_at": item.created_at,
            }
        )

    plans = Plan.objects.filter(student=user).order_by("-created_at")[: max_rows]
    for item in plans:
        text = (item.extracted_text or "").strip()
        if not text:
            continue
        rows.append(
            {
                "source_type": "plan",
                "source_id": item.id,
                "title": f"方案 · {item.title} V{item.version}",
                "text": text[:5000],
                "created_at": item.created_at,
            }
        )

    reviews = (
        ReviewRecord.objects.filter(plan__student=user)
        .select_related("plan")
        .order_by("-created_at", "-id")[: max_rows]
    )
    for item in reviews:
        segments = _collect_review_segments(item)
        text = "\n".join([seg for seg in segments if seg]).strip()
        if not text:
            continue
        rows.append(
            {
                "source_type": "review",
                "source_id": item.id,
                "title": f"检阅({item.audience_role}) · {item.plan.title if item.plan else '-'}",
                "text": text[:3500],
                "created_at": item.created_at,
            }
        )
    return rows


def _build_dimension_payload(rows: list[dict[str, Any]], limit_per_dimension: int = 10) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    evidence_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scored_dimensions: list[dict[str, Any]] = []

    for dim in DIMENSIONS:
        hits: list[dict[str, Any]] = []
        for row in rows:
            text = row.get("text") or ""
            matched_keywords = _text_contains_any(text, dim.keywords)
            if not matched_keywords:
                continue
            match_score = _match_score_for_row(row, matched_keywords=matched_keywords, total_keywords=len(dim.keywords))
            hits.append(
                {
                    "source_type": row.get("source_type"),
                    "source_id": row.get("source_id"),
                    "title": row.get("title"),
                    "snippet": _clip(text, 200),
                    "created_at": row.get("created_at"),
                    "keywords": matched_keywords[:4],
                    "match_score": match_score,
                    "keyword_hit_count": len(matched_keywords),
                }
            )
        hits.sort(
            key=lambda item: (
                float(item.get("match_score") or 0.0),
                _row_timestamp(item.get("created_at")),
            ),
            reverse=True,
        )
        hits = _pick_balanced_hits(hits, limit_per_dimension=limit_per_dimension)

        evidence_map[dim.key] = hits
        score = _score_from_hits(hits, keyword_size=len(dim.keywords))
        summary = dim.summary_hint if score >= 3.25 else dim.weakness_hint
        scored_dimensions.append(
            {
                "key": dim.key,
                "label": dim.label,
                "score": round(score, 2),
                "summary": summary,
                "evidence_count": len(hits),
            }
        )

    return scored_dimensions, evidence_map


def _rank_strengths_and_gaps(dimensions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(dimensions, key=lambda x: float(x.get("score") or 0), reverse=True)
    strengths = ordered[:2]
    gaps = list(reversed(ordered[-2:])) if ordered else []
    return strengths, gaps


def build_student_persona(user: User) -> dict[str, Any]:
    rows = _collect_student_artifacts(user)
    dimensions, evidence_map = _build_dimension_payload(rows)
    strengths, improvements = _rank_strengths_and_gaps(dimensions)

    radar = [{"key": item["key"], "name": item["label"], "value": item["score"]} for item in dimensions]
    avg_score = round(sum(float(item.get("score") or 0) for item in dimensions) / max(len(dimensions), 1), 2)

    return {
        "subject": {"id": user.id, "username": user.username, "role": user.role},
        "updated_at": timezone.now().isoformat(),
        "artifact_count": len(rows),
        "average_score": avg_score,
        "dimensions": dimensions,
        "radar": radar,
        "strengths": strengths,
        "improvements": improvements,
        "evidence_map": evidence_map,
    }


def resolve_peer_student_ids(student: User, limit: int = 80) -> list[int]:
    teacher_ids = list(MentorshipRelation.objects.filter(student=student).values_list("teacher_id", flat=True))
    if teacher_ids:
        ids = list(
            MentorshipRelation.objects.filter(teacher_id__in=teacher_ids)
            .values_list("student_id", flat=True)
            .distinct()
        )
        ids = [sid for sid in ids if sid != student.id]
        return ids[:limit]

    # Fallback: use active student pool as pseudo-class scope.
    return list(
        User.objects.filter(role=getattr(User, "ROLE_STUDENT", "student"), is_active=True)
        .exclude(id=student.id)
        .values_list("id", flat=True)[:limit]
    )


def build_class_persona(student_ids: list[int], class_name: str = "班级画像") -> dict[str, Any]:
    ids = [int(i) for i in student_ids if str(i).isdigit()]
    if not ids:
        empty_dimensions = [{"key": dim.key, "label": dim.label, "score": 0.0, "summary": "暂无数据", "evidence_count": 0} for dim in DIMENSIONS]
        return {
            "class_name": class_name,
            "updated_at": timezone.now().isoformat(),
            "student_count": 0,
            "average_score": 0.0,
            "dimensions": empty_dimensions,
            "radar": [{"key": row["key"], "name": row["label"], "value": row["score"]} for row in empty_dimensions],
            "strengths": [],
            "improvements": [],
            "evidence_map": {dim.key: [] for dim in DIMENSIONS},
        }

    students = list(User.objects.filter(id__in=ids))
    persona_rows = [build_student_persona(user) for user in students]

    dim_bucket: dict[str, list[float]] = defaultdict(list)
    evidence_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for student, persona in zip(students, persona_rows):
        for dim in persona.get("dimensions") or []:
            key = str(dim.get("key") or "")
            if not key:
                continue
            dim_bucket[key].append(float(dim.get("score") or 0))
        for key, rows in (persona.get("evidence_map") or {}).items():
            for row in rows[:4]:
                mapped = dict(row or {})
                mapped["student_id"] = student.id
                mapped["student_name"] = student.display_name
                evidence_map[key].append(mapped)

    dimensions: list[dict[str, Any]] = []
    for dim in DIMENSIONS:
        vals = dim_bucket.get(dim.key) or []
        rows = evidence_map.get(dim.key) or []
        score_base = (sum(vals) / len(vals)) if vals else 0.0
        source_diversity = len({str(x.get("source_type") or "") for x in rows if str(x.get("source_type") or "").strip()}) / max(len(SOURCE_QUALITY_WEIGHT), 1)
        keyword_union: set[str] = set()
        for row in rows:
            for kw in row.get("keywords") or []:
                if str(kw).strip():
                    keyword_union.add(str(kw).strip().lower())
        keyword_coverage = len(keyword_union) / max(len(dim.keywords), 1)
        evidence_signal = min(0.62, math.log1p(len(rows)) * 0.21)
        spread = max(vals) - min(vals) if len(vals) >= 2 else 0.0
        adjustment = ((keyword_coverage - 0.42) * 0.52) + ((source_diversity - 0.45) * 0.36) + evidence_signal + min(0.22, spread * 0.09)
        score = round(max(0.0, min(5.0, score_base + adjustment)), 2) if vals else 0.0
        summary = dim.summary_hint if score >= 3.25 else dim.weakness_hint
        dimensions.append(
            {
                "key": dim.key,
                "label": dim.label,
                "score": score,
                "summary": summary,
                "evidence_count": len(evidence_map.get(dim.key) or []),
            }
        )

    strengths, improvements = _rank_strengths_and_gaps(dimensions)
    avg_score = round(sum(float(item.get("score") or 0) for item in dimensions) / max(len(dimensions), 1), 2)

    trimmed_evidence = {}
    for dim in DIMENSIONS:
        rows = evidence_map.get(dim.key) or []
        rows = sorted(rows, key=lambda item: float(item.get("match_score") or 0.0), reverse=True)
        trimmed_evidence[dim.key] = rows[:30]

    return {
        "class_name": class_name,
        "updated_at": timezone.now().isoformat(),
        "student_count": len(students),
        "average_score": avg_score,
        "dimensions": dimensions,
        "radar": [{"key": item["key"], "name": item["label"], "value": item["score"]} for item in dimensions],
        "strengths": strengths,
        "improvements": improvements,
        "evidence_map": trimmed_evidence,
    }


def build_teacher_class_persona(teacher: User) -> dict[str, Any]:
    student_ids = list(MentorshipRelation.objects.filter(teacher=teacher).values_list("student_id", flat=True))
    return build_class_persona(student_ids=student_ids, class_name=f"{teacher.username} 指导班级画像")


def build_student_class_persona(student: User) -> dict[str, Any]:
    peer_ids = resolve_peer_student_ids(student)
    return build_class_persona(student_ids=peer_ids, class_name="同伴班级画像")
