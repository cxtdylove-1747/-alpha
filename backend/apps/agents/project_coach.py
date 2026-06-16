from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from ..core.services.rule_engine import RuleEngine


class ProjectCoach:
    def diagnose(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        engine = RuleEngine()
        triggered = [asdict(item) for item in engine.evaluate(facts)]
        if not triggered:
            return {
                "diagnosis": "暂未发现高风险瓶颈。",
                "evidence": "当前规则检查未触发高优先级问题。",
                "impact": "可继续推进MVP验证与路演准备。",
                "next_task": {
                    "description": "补充3条最新用户证据并更新计划。",
                    "template": "unit_economics_template.xlsx",
                    "acceptance_criteria": "证据链齐全且核心假设可验证",
                },
            }

        severity_order = {"high": 3, "medium": 2, "low": 1}
        top = sorted(triggered, key=lambda x: severity_order.get(x.get("severity"), 0), reverse=True)[0]
        return {
            "diagnosis": top["description"],
            "evidence": top["trigger_message"],
            "impact": top["impact"],
            "next_task": {
                "description": top["fix_task"],
                "template": "unit_economics_template.xlsx",
                "acceptance_criteria": "提交更新证据后重新评估且高风险规则不再触发",
            },
            "triggered_rules": triggered,
        }


