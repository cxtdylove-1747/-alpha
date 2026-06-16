from __future__ import annotations

from typing import Any, Dict, List

from ..core.services.hypergraph_runtime import get_hypergraph_client
from ..core.services.llm_gateway import call_llm
from ..core.services.vector_retrieval import VectorRetrievalService

TUTOR_SYSTEM_PROMPT = (
    "你是创新创业学习导师。"
    "每次回答都要包含：定义、关键要点、为什么重要、通俗例子、常见误区、练习题。"
    "优先给出可执行建议，避免空话。"
)

KNOWLEDGE_BASE = {
    "PMF": {
        "definition": "PMF 指产品与市场匹配，意味着目标用户愿意持续使用并愿意付费。",
        "mistake": "只讲功能，不验证用户行为和支付意愿。",
        "task": "设计两周 PMF 验证实验，至少访谈 10 位目标用户。",
    },
    "TAM": {
        "definition": "TAM 是总可服务市场规模，用于定义市场天花板。",
        "mistake": "把 TAM 当作短期可获取市场，忽略 SAM/SOM 分层。",
        "task": "按区域和人群重估 TAM/SAM/SOM，并说明数据来源。",
    },
}


class TutorAgent:
    TOPIC_LIST = [
        "商业模式画布（BMC）",
        "TAM / SAM / SOM 市场规模",
        "PMF 产品市场匹配",
        "护城河（竞争壁垒）",
        "用户访谈与需求验证",
        "竞品分析",
        "盈利模式与单位经济模型",
        "MVP 最小可行产品",
        "路演逻辑与表达",
        "财务预测基础",
    ]

    def _history_text(self, history: list[dict[str, Any]] | None, max_chars: int = 1200) -> str:
        rows = history if isinstance(history, list) else []
        chunks: List[str] = []
        for item in rows[-8:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or item.get("text") or "").strip()
            if not content:
                continue
            chunks.append(f"{role}: {content}" if role else content)
        return "\n".join(chunks)[:max_chars]

    def _kg_trace_for_query(self, query: str, limit: int = 6) -> List[Dict[str, str]]:
        client = get_hypergraph_client()
        if not client:
            return []

        node_ids = client.extract_entities_from_text(str(query or "")[:1800])[:120]
        traces: List[Dict[str, str]] = []
        seen = set()
        for node_id in node_ids:
            nid = str(node_id or "").strip()
            if not nid or nid in seen:
                continue
            seen.add(nid)

            node = client.get_node(nid) or {}
            props = node.get("properties") or {}
            label = str(node.get("label") or "Entity").strip() or "Entity"
            name = str(props.get("name") or nid).strip() or nid
            source = props.get("source") or {}
            if isinstance(source, list):
                source = source[0] if source else {}
            if not isinstance(source, dict):
                source = {}

            traces.append(
                {
                    "node_id": nid,
                    "label": label,
                    "name": name,
                    "source_file": str(source.get("file") or "").strip(),
                    "source_text": str(source.get("text") or "").strip()[:120],
                }
            )
            if len(traces) >= limit:
                break
        return traces

    def teach(self, topic: str) -> Dict[str, Any]:
        normalized = (topic or "").strip().upper()
        item = KNOWLEDGE_BASE.get(normalized) or {
            "definition": f"{topic} 是创新创业中的关键概念，建议从定义、应用和验证三层理解。",
            "mistake": "只记概念，不做实证验证。",
            "task": f"围绕 {topic} 设计一个可执行实验并输出实验记录。",
        }

        recall = VectorRetrievalService().recall_cases(query=f"{topic} 创新创业案例", top_k=1)
        case_text = "可从优秀案例中提炼可复用方法。"
        if recall:
            case_text = f"案例参考：{recall[0].get('title')}（行业：{recall[0].get('industry')}）"

        kg_traces = self._kg_trace_for_query(topic)

        return {
            "topic": topic,
            "definition": item["definition"],
            "case": case_text,
            "common_mistake": item["mistake"],
            "practice_task": item["task"],
            "expected_artifact": "实验报告模板（含目标、方法、数据、结论）",
            "rubric_mapping": ["R1", "R2", "R7"],
            "kg_traces": kg_traces,
        }

    def opening(self) -> Dict[str, Any]:
        return {
            "message": "请选择你想学习的知识点，我会先讲解再带你做练习题。",
            "topics": self.TOPIC_LIST,
            "kg_enabled": bool(get_hypergraph_client()),
        }

    def chat(self, message: str, history: list[dict[str, Any]] | None = None) -> Dict[str, Any]:
        text = (message or "").strip()
        if not text:
            return self.opening()

        history_text = self._history_text(history)
        kg_traces = self._kg_trace_for_query(f"{text}\n{history_text}")
        kg_lines = "\n".join(
            [
                f"- [{row['label']}] {row['name']} ({row['node_id']})"
                + (f" | 来源: {row['source_file']}" if row.get("source_file") else "")
                for row in kg_traces
            ]
        )

        prompt = (
            "你是创新创业学习导师。请按以下结构回答：\n"
            "1) 定义\n2) 核心要点\n3) 为什么重要\n4) 通俗例子\n5) 常见误区\n6) 练习题（至少2题，附参考答案）\n"
            "若提供了知识图谱线索，请在相关段落引用它们。\n"
            f"用户提问：{text}\n"
            f"历史对话：{history_text}\n"
            f"知识图谱线索：\n{kg_lines or '- 暂无命中'}"
        )

        llm = call_llm(prompt=prompt, system_prompt=TUTOR_SYSTEM_PROMPT, temperature=0.3, timeout_seconds=45)
        if not llm:
            raise RuntimeError("出了点问题，请稍后重试")
        return {"message": llm, "kg_traces": kg_traces}
