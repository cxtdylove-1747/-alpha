from __future__ import annotations

from typing import Any, Dict, List

QUESTION_BANK = [
    {"type": "market", "question": "你的目标市场规模依据是什么？请给出数据来源。"},
    {"type": "technology", "question": "你的关键技术壁垒是什么？3个月内如何验证？"},
    {"type": "finance", "question": "请解释你的CAC、LTV和回本周期假设。"},
    {"type": "competition", "question": "如果头部公司复制你的产品，你的防御策略是什么？"},
    {"type": "team", "question": "团队当前能力缺口在哪里？如何补齐？"},
    {"type": "compliance", "question": "项目涉及隐私/合规时，你有哪些控制措施？"},
]


class RoadmapSimulator:
    def __init__(self) -> None:
        self.questions = QUESTION_BANK

    def next_turn(self, question_index: int, answer: str) -> Dict[str, Any]:
        idx = max(0, int(question_index or 0))
        score, feedback = self._evaluate_answer(answer)
        next_idx = idx + 1
        next_question = self.questions[next_idx]["question"] if next_idx < len(self.questions) else None
        return {
            "current_index": idx,
            "score": score,
            "feedback": feedback,
            "next_index": next_idx,
            "next_question": next_question,
            "is_finished": next_question is None,
        }

    def start(self) -> Dict[str, Any]:
        return {
            "message": "欢迎进入路演模拟。请先用1分钟介绍项目。",
            "question_index": 0,
            "question": self.questions[0]["question"],
        }

    def build_report(self, turns: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not turns:
            return {"avg_score": 0, "highlights": [], "weaknesses": ["缺少有效回答"], "training_focus": ["先完成首轮模拟"]}
        scores = [float(item.get("score") or 0) for item in turns]
        avg_score = round(sum(scores) / len(scores), 2)
        highlights = ["回答结构完整", "能给出行动路径"] if avg_score >= 3 else ["愿意迭代项目"]
        weaknesses = ["证据引用不足", "财务与竞争应对仍需量化"] if avg_score < 4 else ["需要补充更多可验证指标"]
        return {
            "avg_score": avg_score,
            "highlights": highlights,
            "weaknesses": weaknesses,
            "training_focus": ["强化数据证据", "准备高压追问的反驳逻辑"],
        }

    def _evaluate_answer(self, answer: str) -> tuple[int, str]:
        text = (answer or "").strip()
        if len(text) < 20:
            return 1, "回答过短，建议给出数据、依据和可执行计划。"
        if any(k in text for k in ["数据", "访谈", "验证", "指标"]):
            return 4, "回答包含证据意识，建议补充更明确的量化目标。"
        return 3, "回答方向正确，建议补充可验证数据和时间节点。"

