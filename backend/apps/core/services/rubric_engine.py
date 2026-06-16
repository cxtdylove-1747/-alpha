from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from apps.core.models import RubricItem


DEFAULT_RUBRIC_ITEMS: List[Dict[str, Any]] = [
    {"rubric_id": "R1", "name": "问题定义", "weight": 0.10, "description": "问题清晰且基于真实痛点", "required_evidence": ["用户访谈", "调研"]},
    {"rubric_id": "R2", "name": "用户证据强度", "weight": 0.15, "description": "主张有充分证据支持", "required_evidence": ["访谈引用", "行为数据"]},
    {"rubric_id": "R3", "name": "方案可行性", "weight": 0.10, "description": "方案技术与执行可行", "required_evidence": ["技术路线", "资源匹配"]},
    {"rubric_id": "R4", "name": "商业模式一致性", "weight": 0.15, "description": "客户价值渠道与收入一致", "required_evidence": ["商业模式画布"]},
    {"rubric_id": "R5", "name": "市场与竞争", "weight": 0.10, "description": "市场规模与竞品分析合理", "required_evidence": ["TAM/SAM/SOM", "竞品对比表"]},
    {"rubric_id": "R6", "name": "财务逻辑", "weight": 0.10, "description": "单位经济与财务假设合理", "required_evidence": ["单位经济", "现金流"]},
    {"rubric_id": "R7", "name": "创新与差异化", "weight": 0.10, "description": "差异化优势可验证", "required_evidence": ["对比矩阵"]},
    {"rubric_id": "R8", "name": "团队与执行", "weight": 0.05, "description": "团队能力与里程碑匹配", "required_evidence": ["团队简介", "里程碑"]},
    {"rubric_id": "R9", "name": "展示与材料质量", "weight": 0.05, "description": "材料逻辑清晰有说服力", "required_evidence": ["路演PPT"]},
]


@dataclass
class RubricScore:
    rubric_id: str
    score: float
    evidence_quotes: List[Dict[str, Any]]


class RubricEngine:
    def bootstrap_defaults(self) -> None:
        for item in DEFAULT_RUBRIC_ITEMS:
            RubricItem.objects.update_or_create(
                rubric_id=item["rubric_id"],
                defaults=item,
            )

    def evaluate(self, text: str, facts: Dict[str, Any]) -> List[RubricScore]:
        content = text or ""
        scores: List[RubricScore] = []

        for item in RubricItem.objects.filter(is_active=True).order_by("rubric_id"):
            raw = self._score_item(item.rubric_id, content, facts)
            scores.append(
                RubricScore(
                    rubric_id=item.rubric_id,
                    score=raw,
                    evidence_quotes=self._collect_evidence(item.rubric_id, content),
                )
            )
        return scores

    def _score_item(self, rubric_id: str, text: str, facts: Dict[str, Any]) -> float:
        base = 5.0
        if rubric_id == "R1" and "痛点" in text:
            base += 2
        if rubric_id == "R2" and facts.get("user_interview_count", 0) >= 5:
            base += 2
        if rubric_id == "R3" and "里程碑" in text:
            base += 1.5
        if rubric_id == "R4" and facts.get("customer_segment") == facts.get("value_proposition_target"):
            base += 2
        if rubric_id == "R5" and facts.get("tam", 0) >= facts.get("sam", 0) >= facts.get("som", 0) > 0:
            base += 2
        if rubric_id == "R6" and facts.get("ltv", 0) > facts.get("cac", 0):
            base += 2
        if rubric_id == "R7" and facts.get("innovation_claim", {}).get("has_verifiable_metric"):
            base += 2
        if rubric_id == "R8" and not facts.get("any_milestone_without_resource"):
            base += 2
        if rubric_id == "R9" and not facts.get("pitch_deck_has_story_gap"):
            base += 2
        return round(max(0, min(10, base)), 2)

    def _collect_evidence(self, rubric_id: str, text: str) -> List[Dict[str, Any]]:
        hints = {
            "R1": ["痛点", "用户"],
            "R2": ["访谈", "问卷"],
            "R3": ["技术", "里程碑"],
            "R4": ["商业模式", "价值主张"],
            "R5": ["TAM", "SAM", "SOM", "竞品"],
            "R6": ["LTV", "CAC", "现金流"],
            "R7": ["创新", "差异化"],
            "R8": ["团队", "执行"],
            "R9": ["路演", "PPT"],
        }
        evidence: List[Dict[str, Any]] = []
        for key in hints.get(rubric_id, []):
            pos = text.find(key)
            if pos >= 0:
                start = max(0, pos - 18)
                end = min(len(text), pos + 40)
                evidence.append({"page": 1, "quote": text[start:end], "keyword": key})
        return evidence[:3]

