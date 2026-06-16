from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from ..models import Rule


@dataclass
class TriggeredRule:
    rule_id: str
    severity: str
    description: str
    trigger_message: str
    impact: str
    fix_task: str


DEFAULT_HARD_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "H1",
        "rule_type": "BusinessModelConsistency",
        "description": "客户与价值主张错位",
        "severity": "high",
        "condition": "customer_segment != value_proposition_target",
        "trigger_message": "你定义的目标客户是{customer_segment}，但价值主张目标是{value_proposition_target}，两者不一致。",
        "impact": "商业模式执行风险高，付费意愿弱。",
        "fix_task": "重新定义目标客户并补充至少3条访谈证据。",
    },
    {
        "rule_id": "H2",
        "rule_type": "ChannelMismatch",
        "description": "渠道与客户触达不匹配",
        "severity": "medium",
        "condition": "channel not in customer_reachable_channels",
        "trigger_message": "当前渠道{channel}不在用户高频触达渠道中。",
        "impact": "获客效率低。",
        "fix_task": "补充用户触达路径并验证转化率。",
    },
    {
        "rule_id": "H3",
        "rule_type": "PaymentEvidence",
        "description": "缺少支付意愿证据",
        "severity": "high",
        "condition": "has_willingness_to_pay_evidence == false",
        "trigger_message": "暂无支付意愿证据，收入假设风险高。",
        "impact": "收入模型缺乏验证。",
        "fix_task": "补充支付意愿访谈和小额付费测试。",
    },
    {
        "rule_id": "H4",
        "rule_type": "MarketSizing",
        "description": "TAM/SAM/SOM逻辑错误",
        "severity": "high",
        "condition": "tam < sam or sam < som or som <= 0",
        "trigger_message": "TAM/SAM/SOM层级关系异常。",
        "impact": "市场规模判断失真。",
        "fix_task": "按可达市场重新估算规模。",
    },
    {
        "rule_id": "H5",
        "rule_type": "EvidenceVolume",
        "description": "用户调研样本不足",
        "severity": "medium",
        "condition": "user_interview_count < 5 and survey_sample < 50",
        "trigger_message": "访谈和问卷样本量不足。",
        "impact": "需求结论可信度低。",
        "fix_task": "增加访谈和问卷样本。",
    },
    {
        "rule_id": "H6",
        "rule_type": "CompetitionAnalysis",
        "description": "竞品分析缺少功能对比",
        "severity": "medium",
        "condition": "competitor_analysis.has_feature_comparison == false",
        "trigger_message": "未提供竞品功能对比矩阵。",
        "impact": "差异化说服力不足。",
        "fix_task": "补充功能与价格对比表。",
    },
    {
        "rule_id": "H7",
        "rule_type": "InnovationClaim",
        "description": "创新主张缺少可验证指标",
        "severity": "medium",
        "condition": "innovation_claim.has_verifiable_metric == false",
        "trigger_message": "创新点缺少量化验证指标。",
        "impact": "创新性无法被评审快速确认。",
        "fix_task": "补充至少1个可验证指标。",
    },
    {
        "rule_id": "H8",
        "rule_type": "UnitEconomics",
        "description": "LTV不大于CAC",
        "severity": "high",
        "condition": "ltv <= cac",
        "trigger_message": "当前LTV={ltv}，CAC={cac}，单位经济不可持续。",
        "impact": "现金流风险高。",
        "fix_task": "优化获客效率并提高复购/ARPU。",
    },
    {
        "rule_id": "H9",
        "rule_type": "GrowthLoop",
        "description": "增长策略缺少留存",
        "severity": "medium",
        "condition": "growth_strategy_missing_retention == true",
        "trigger_message": "增长策略未覆盖留存机制。",
        "impact": "增长不可持续。",
        "fix_task": "增加留存指标和用户运营动作。",
    },
    {
        "rule_id": "H10",
        "rule_type": "ExecutionPlan",
        "description": "里程碑未绑定资源",
        "severity": "medium",
        "condition": "any_milestone_without_resource == true",
        "trigger_message": "存在里程碑无资源支撑。",
        "impact": "执行落地风险高。",
        "fix_task": "补充人力/预算/时间资源映射。",
    },
    {
        "rule_id": "H11",
        "rule_type": "Compliance",
        "description": "涉及隐私但缺少合规方案",
        "severity": "high",
        "condition": "involves_data_privacy and not has_compliance_plan",
        "trigger_message": "涉及隐私数据但尚无合规方案。",
        "impact": "合规与法律风险高。",
        "fix_task": "补充数据合规与授权流程。",
    },
    {
        "rule_id": "H12",
        "rule_type": "TRLFunding",
        "description": "TRL较低且资金缺口大",
        "severity": "high",
        "condition": "tech_trl < 3 and required_funding > available_budget",
        "trigger_message": "技术成熟度与预算不匹配。",
        "impact": "研发计划无法按时推进。",
        "fix_task": "降低阶段目标或增加资金来源。",
    },
    {
        "rule_id": "H13",
        "rule_type": "MvpValidation",
        "description": "MVP缺少成功指标",
        "severity": "medium",
        "condition": "mvp_test_has_no_success_metric == true",
        "trigger_message": "MVP测试缺少成功判定标准。",
        "impact": "实验无法驱动决策。",
        "fix_task": "定义可量化验收指标。",
    },
    {
        "rule_id": "H14",
        "rule_type": "PitchNarrative",
        "description": "路演故事线断裂",
        "severity": "low",
        "condition": "pitch_deck_has_story_gap == true",
        "trigger_message": "路演材料故事线存在断点。",
        "impact": "表达说服力下降。",
        "fix_task": "按问题-方案-证据-商业闭环重构叙事。",
    },
    {
        "rule_id": "H15",
        "rule_type": "EvidenceCompleteness",
        "description": "Rubric证据不足",
        "severity": "medium",
        "condition": "rubric_evidence_provided < required_evidence",
        "trigger_message": "Rubric证据数量不足。",
        "impact": "评分上限受限。",
        "fix_task": "补齐缺失证据并标注来源。",
    },
]


class RuleEngine:
    def bootstrap_defaults(self) -> None:
        for item in DEFAULT_HARD_RULES:
            Rule.objects.update_or_create(
                rule_id=item["rule_id"],
                defaults=item,
            )

    def evaluate(self, facts: Dict[str, Any]) -> List[TriggeredRule]:
        triggered: List[TriggeredRule] = []
        for rule in Rule.objects.filter(is_active=True).order_by("rule_id"):
            if self._match(rule.rule_id, facts):
                triggered.append(
                    TriggeredRule(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        description=rule.description,
                        trigger_message=self._render(rule.trigger_message, facts),
                        impact=rule.impact,
                        fix_task=rule.fix_task,
                    )
                )
        return triggered

    def _render(self, template: str, facts: Dict[str, Any]) -> str:
        try:
            return template.format(**facts)
        except Exception:
            return template

    def _match(self, rule_id: str, facts: Dict[str, Any]) -> bool:
        v = facts
        if rule_id == "H1":
            return v.get("customer_segment") != v.get("value_proposition_target")
        if rule_id == "H2":
            return v.get("channel") not in (v.get("customer_reachable_channels") or [])
        if rule_id == "H3":
            return not bool(v.get("has_willingness_to_pay_evidence"))
        if rule_id == "H4":
            tam = float(v.get("tam") or 0)
            sam = float(v.get("sam") or 0)
            som = float(v.get("som") or 0)
            return tam < sam or sam < som or som <= 0
        if rule_id == "H5":
            return int(v.get("user_interview_count") or 0) < 5 and int(v.get("survey_sample") or 0) < 50
        if rule_id == "H6":
            return not bool((v.get("competitor_analysis") or {}).get("has_feature_comparison"))
        if rule_id == "H7":
            return not bool((v.get("innovation_claim") or {}).get("has_verifiable_metric"))
        if rule_id == "H8":
            return float(v.get("ltv") or 0) <= float(v.get("cac") or 0)
        if rule_id == "H9":
            return bool(v.get("growth_strategy_missing_retention"))
        if rule_id == "H10":
            return bool(v.get("any_milestone_without_resource"))
        if rule_id == "H11":
            return bool(v.get("involves_data_privacy")) and not bool(v.get("has_compliance_plan"))
        if rule_id == "H12":
            return float(v.get("tech_trl") or 0) < 3 and float(v.get("required_funding") or 0) > float(v.get("available_budget") or 0)
        if rule_id == "H13":
            return bool(v.get("mvp_test_has_no_success_metric"))
        if rule_id == "H14":
            return bool(v.get("pitch_deck_has_story_gap"))
        if rule_id == "H15":
            return float(v.get("rubric_evidence_provided") or 0) < float(v.get("required_evidence") or 0)
        return False


