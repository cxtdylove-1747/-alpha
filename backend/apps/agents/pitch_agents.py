from __future__ import annotations

import re
from typing import Any, Dict, List

from ..core.services.llm_gateway import call_llm

OPTIMIZE_SYSTEM_PROMPT = """你是资深创新创业路演优化导师，只做优化、不代写、不编造信息。
规则：
1) 必须先有项目方案；PPT/讲稿可选。
2) 默认路演时长6分钟，若用户明确指定则覆盖默认时长。
3) 无PPT/讲稿时，不生成全文，只给结构思路与优化方向。
4) 输出聚焦1-2个最关键问题，给可落地表达模板。"""

SIMULATION_SYSTEM_PROMPT = """你是严格、专业、一针见血的路演评委。
绝对约束：
1) 未开始模拟：不对话、不建议；
2) 模拟中：只提问，不解释、不闲聊；
3) 结束模拟后：才可解释评委打分逻辑与改进建议。"""

EXPERT_QUESTION_BANKS = {
    "balanced_judge": {
        "label": "综合型评委",
        "questions": [
            "你的痛点证据来自哪些用户样本？样本量和结论分别是什么？",
            "如果头部竞品进入，你的差异化壁垒和防御策略是什么？",
            "请解释你的CAC、LTV与回本周期，关键假设依据是什么？",
            "你的核心技术可行性如何在3个月内被验证？",
            "团队当前能力短板在哪里，如何补齐？",
            "合规与数据隐私方面，你准备了哪些控制措施？",
        ],
    },
    "aggressive_vc": {
        "label": "激进型VC",
        "questions": [
            "你凭什么在12个月内把收入做到3倍增长？关键增长杠杆分别是什么？",
            "如果我今天不投，你下一轮还能靠什么数据打动更高估值投资人？",
            "你的用户增长如果低于预期30%，现金流还能撑多久？",
            "面对同赛道融资更快的对手，你的速度壁垒和资金使用效率如何证明？",
            "请给出你未来18个月最关键的3个里程碑及失败止损线。",
            "你要这笔钱最先砸在哪三件事上，为什么这不是可推迟项？",
        ],
    },
    "technical_expert": {
        "label": "技术流专家",
        "questions": [
            "你的核心技术架构是什么？哪些模块是自主可控、哪些依赖第三方？",
            "请说明当前方案的性能瓶颈、压测结果和扩容路径。",
            "关键算法或模型的准确率、召回率及误差边界是多少？",
            "如果业务规模提升10倍，系统在稳定性与成本上如何演进？",
            "你如何确保数据质量、可追溯性和模型版本可回滚？",
            "请列出技术路线中最高风险的两项假设，以及对应验证计划。",
        ],
    },
    "conservative_banker": {
        "label": "保守型银行家",
        "questions": [
            "你的还款来源与现金流覆盖倍数如何证明？请给出最保守场景。",
            "如果行业景气下行，你的坏账与违约风险如何控制？",
            "你当前资产负债结构是否健康？有哪些流动性风险点？",
            "请解释你的单位经济模型在低增长情况下是否仍可持续。",
            "你有哪些合规资质或审计安排，能降低金融机构的审查成本？",
            "若融资成本上升2个百分点，你的项目还能维持正向回报吗？",
        ],
    },
}

EXPERT_TYPE_ALIASES = {
    "vc": "aggressive_vc",
    "aggressivevc": "aggressive_vc",
    "aggressive_vc": "aggressive_vc",
    "激进型vc": "aggressive_vc",
    "激进vc": "aggressive_vc",
    "technical": "technical_expert",
    "technical_expert": "technical_expert",
    "技术流专家": "technical_expert",
    "保守型银行家": "conservative_banker",
    "conservative_banker": "conservative_banker",
    "banker": "conservative_banker",
    "综合型评委": "balanced_judge",
    "balanced": "balanced_judge",
    "balanced_judge": "balanced_judge",
}


class PitchOptimizeAgent:
    def chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload.get("plan_text"):
            return {"ok": False, "message": "请先选择并提交项目方案（PDF/Word）后再进行优化对话。"}

        question = str(payload.get("message") or "").strip()
        duration = self._extract_minutes(question) or int(payload.get("duration_minutes") or 6)

        prompt = (
            f"路演目标时长：{duration}分钟\n"
            f"方案摘要：{str(payload.get('plan_text') or '')[:2500]}\n"
            f"PPT信息：{str(payload.get('ppt_name') or '未提交')}\n"
            f"讲稿信息：{str(payload.get('script_name') or payload.get('script_text') or '未提交')}\n"
            f"用户问题：{question or '请先给我本轮最关键的优化建议'}\n"
            "请输出：\n"
            "1) 最关键问题（1-2条）\n"
            "2) 优化建议\n"
            "3) 可直接套用表达句式\n"
            "4) 6分钟时间分配建议（或按用户时长）"
        )
        llm = call_llm(prompt=prompt, system_prompt=OPTIMIZE_SYSTEM_PROMPT, temperature=0.3, timeout_seconds=0)
        if llm:
            return {"ok": True, "duration_minutes": duration, "answer": llm}

        return {"ok": False, "duration_minutes": duration, "message": "出了些小问题"}

    @staticmethod
    def _extract_minutes(text: str) -> int | None:
        if not text:
            return None
        m = re.search(r"(\d{1,2})\s*分钟", text)
        if not m:
            return None
        try:
            return max(1, min(30, int(m.group(1))))
        except Exception:
            return None


class PitchSimulationAgent:
    @staticmethod
    def _normalize_expert_type(payload: Dict[str, Any]) -> str:
        raw_type = payload.get("expert_type")
        if not raw_type:
            candidate = payload.get("expert_types")
            if isinstance(candidate, list) and candidate:
                raw_type = candidate[0]
            elif isinstance(candidate, str):
                raw_type = candidate.split(",")[0]

        key = str(raw_type or "").strip().lower()
        mapped = EXPERT_TYPE_ALIASES.get(key, key)
        if mapped in EXPERT_QUESTION_BANKS:
            return mapped
        return "balanced_judge"

    @staticmethod
    def _resolve_expert_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
        expert_type = PitchSimulationAgent._normalize_expert_type(payload)
        profile = EXPERT_QUESTION_BANKS.get(expert_type) or EXPERT_QUESTION_BANKS["balanced_judge"]
        questions = profile.get("questions") or EXPERT_QUESTION_BANKS["balanced_judge"]["questions"]
        return {
            "expert_type": expert_type,
            "expert_label": profile.get("label") or "综合型评委",
            "questions": questions,
        }

    def start(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload.get("ppt_name") or not payload.get("script_file_name"):
            return {"ok": False, "message": "开始模拟前必须提交路演PPT和讲稿文件。"}
        profile = self._resolve_expert_profile(payload)
        questions: List[str] = profile["questions"]
        return {
            "ok": True,
            "mode": "simulating",
            "expert_type": profile["expert_type"],
            "expert_label": profile["expert_label"],
            "question_index": 0,
            "question": questions[0],
            "message": f"已进入【{profile['expert_label']}】评委模拟模式。接下来我只提问。",
        }

    def ask_next(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        profile = self._resolve_expert_profile(payload)
        questions: List[str] = profile["questions"]
        idx = int(payload.get("question_index") or 0)
        next_idx = min(idx + 1, len(questions) - 1)
        return {
            "ok": True,
            "mode": "simulating",
            "expert_type": profile["expert_type"],
            "expert_label": profile["expert_label"],
            "question_index": next_idx,
            "question": questions[next_idx],
            "only_question": True,
        }

    def end(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        profile = self._resolve_expert_profile(payload)
        turns = payload.get("turns") or []
        score = max(55, min(92, 55 + len(turns) * 4))
        report = {
            "title": "路演模拟评估报告",
            "expert_type": profile["expert_type"],
            "expert_label": profile["expert_label"],
            "logic": "回答结构基本完整，建议增强结论先行。",
            "evidence": "数据支撑存在薄弱项，需补样本与口径说明。",
            "pressure": "抗压表现中等，面对追问时可先给结论再给依据。",
            "weak_points": ["财务假设解释不充分", "壁垒表达不够量化"],
            "improvements": ["准备3组核心数据口径", "补充竞品防御策略一句话版本"],
            "estimated_score": score,
        }
        return {
            "ok": True,
            "mode": "ended",
            "expert_type": profile["expert_type"],
            "expert_label": profile["expert_label"],
            "report": report,
            "message": "模拟已结束，现可继续就本次路演进行答疑。",
        }

    def qa_after_end(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        profile = self._resolve_expert_profile(payload)
        question = str(payload.get("message") or "").strip()
        prompt = (
            f"当前评委类型：{profile['expert_label']}\n"
            f"学生在路演后追问：{question}\n"
            "请解释评委打分逻辑并给补强方向。"
        )
        llm = call_llm(prompt=prompt, system_prompt=SIMULATION_SYSTEM_PROMPT, temperature=0.3, timeout_seconds=0)
        if llm:
            return {
                "ok": True,
                "mode": "qa",
                "expert_type": profile["expert_type"],
                "expert_label": profile["expert_label"],
                "answer": llm,
            }
        return {"ok": False, "mode": "qa", "message": "出了些小问题"}
