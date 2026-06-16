from __future__ import annotations

from typing import Any, Dict, TypedDict

try:  # Optional dependency; fallback path stays functional without LangGraph.
    from langgraph.graph import END, StateGraph  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    END = None
    StateGraph = None

from ..core.services.fact_extractor import extract_facts
from ..core.services.rule_engine import RuleEngine
from ..core.services.rubric_engine import RubricEngine
from ..core.services.vector_retrieval import VectorRetrievalService


class WorkflowState(TypedDict, total=False):
    text: str
    competition: str
    topic: str
    facts: Dict[str, Any]
    triggered_rules: list[dict[str, Any]]
    rubric: list[dict[str, Any]]
    case_recall: list[dict[str, Any]]
    next_step: str
    retrieval_mode: str


class LangGraphWorkflowAgent:
    """LangGraph-style orchestration shim.

    If LangGraph is available in deployment, this class can be upgraded to real StateGraph.
    """

    @staticmethod
    def mode() -> str:
        return "langgraph" if StateGraph is not None else "fallback"

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        state: WorkflowState = {
            "text": str(payload.get("text") or ""),
            "competition": str(payload.get("competition") or "挑战杯"),
            "topic": str(payload.get("topic") or ""),
            "facts": payload.get("facts") or {},
        }

        if StateGraph is None:
            return self._run_fallback(state)
        return self._run_langgraph(state)

    def _run_langgraph(self, state: WorkflowState) -> Dict[str, Any]:
        graph = StateGraph(WorkflowState)
        graph.add_node("collect_facts", self._node_collect_facts)
        graph.add_node("evaluate_rules", self._node_evaluate_rules)
        graph.add_node("score_rubric", self._node_score_rubric)
        graph.add_node("recall_cases", self._node_recall_cases)
        graph.add_node("synthesize", self._node_synthesize)

        graph.set_entry_point("collect_facts")
        graph.add_edge("collect_facts", "evaluate_rules")
        graph.add_edge("evaluate_rules", "score_rubric")
        graph.add_edge("score_rubric", "recall_cases")
        graph.add_edge("recall_cases", "synthesize")
        graph.add_edge("synthesize", END)

        chain = graph.compile()
        result = chain.invoke(state)
        return {
            "workflow": "langgraph: collect_facts -> evaluate_rules -> score_rubric -> recall_cases -> synthesize",
            "facts": result.get("facts", {}),
            "triggered_rules": result.get("triggered_rules", []),
            "rubric": result.get("rubric", []),
            "case_recall": result.get("case_recall", []),
            "retrieval_mode": result.get("retrieval_mode", VectorRetrievalService().retrieval_mode()),
            "next_step": result.get("next_step", "优先修复高风险规则。"),
        }

    def _run_fallback(self, state: WorkflowState) -> Dict[str, Any]:
        state = self._node_collect_facts(state)
        state = self._node_evaluate_rules(state)
        state = self._node_score_rubric(state)
        state = self._node_recall_cases(state)
        state = self._node_synthesize(state)
        return {
            "workflow": "fallback: collect_facts -> evaluate_rules -> score_rubric -> recall_cases -> synthesize",
            "facts": state.get("facts", {}),
            "triggered_rules": state.get("triggered_rules", []),
            "rubric": state.get("rubric", []),
            "case_recall": state.get("case_recall", []),
            "retrieval_mode": state.get("retrieval_mode", VectorRetrievalService().retrieval_mode()),
            "next_step": state.get("next_step", "优先修复高风险规则。"),
        }

    def _node_collect_facts(self, state: WorkflowState) -> WorkflowState:
        state["facts"] = extract_facts(state.get("text", ""), state.get("facts") or {})
        return state

    def _node_evaluate_rules(self, state: WorkflowState) -> WorkflowState:
        engine = RuleEngine()
        engine.bootstrap_defaults()
        rules = engine.evaluate(state.get("facts") or {})
        state["triggered_rules"] = [item.__dict__ for item in rules]
        return state

    def _node_score_rubric(self, state: WorkflowState) -> WorkflowState:
        engine = RubricEngine()
        engine.bootstrap_defaults()
        scores = engine.evaluate(state.get("text") or "", state.get("facts") or {})
        state["rubric"] = [item.__dict__ for item in scores]
        return state

    def _node_recall_cases(self, state: WorkflowState) -> WorkflowState:
        service = VectorRetrievalService()
        query = f"{state.get('competition', '')} {state.get('topic', '')} {state.get('text', '')}".strip()
        state["case_recall"] = service.recall_cases(query, top_k=3)
        state["retrieval_mode"] = service.retrieval_mode()
        return state

    def _node_synthesize(self, state: WorkflowState) -> WorkflowState:
        high_count = len([item for item in (state.get("triggered_rules") or []) if item.get("severity") == "high"])
        if high_count:
            state["next_step"] = "先修复所有 high 规则，再按 Rubric 薄弱项补证据。"
        else:
            state["next_step"] = "高风险规则已可控，建议进入路演压测与竞赛答辩迭代。"
        return state

