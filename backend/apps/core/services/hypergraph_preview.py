from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from ..models import CaseLibraryDocument
from .llm_gateway import call_llm


def build_preview_graph(limit: int = 80) -> Dict[str, Any]:
    docs = list(CaseLibraryDocument.objects.filter(clean_status=CaseLibraryDocument.CLEAN_DONE)[: max(10, limit)])

    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    seen = set()

    for doc in docs:
        case_id = f"case_{doc.id}"
        nodes.append({"id": case_id, "name": doc.title[:18], "category": "Case", "value": 20})

        industry = (doc.industry_category or "其他").strip() or "其他"
        industry_id = f"industry_{industry}"
        if industry_id not in seen:
            seen.add(industry_id)
            nodes.append({"id": industry_id, "name": industry, "category": "Industry", "value": 14})
        links.append({"source": case_id, "target": industry_id, "name": "IN_INDUSTRY"})

        txt = (doc.extracted_text or "")[:1200]
        concepts = _extract_concepts(txt)
        for concept in concepts:
            cid = f"concept_{concept}"
            if cid not in seen:
                seen.add(cid)
                nodes.append({"id": cid, "name": concept, "category": "Concept", "value": 10})
            links.append({"source": case_id, "target": cid, "name": "EXEMPLIFIES"})

    categories = [{"name": "Case"}, {"name": "Industry"}, {"name": "Concept"}]
    return {"nodes": nodes, "links": links, "categories": categories}


def _extract_concepts(text: str) -> List[str]:
    llm = call_llm(
        prompt=(
            "从以下创新创业文本中提取4个最关键概念，返回JSON数组字符串，如[\"PMF\",\"TAM\"]。"
            f"\n文本：{text[:1200]}"
        ),
        system_prompt="你是双创知识图谱构建助手，只提取概念词，不解释。",
        temperature=0.1,
        timeout_seconds=60,
    )
    if llm:
        raw = llm.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                cleaned = [str(x).strip() for x in arr if str(x).strip()]
                if cleaned:
                    return cleaned[:4]
        except Exception:
            pass

    keywords = ["PMF", "TAM", "SAM", "SOM", "MVP", "护城河", "用户访谈", "单位经济", "路演"]
    hits = []
    upper = text.upper()
    for item in keywords:
        if item.upper() in upper:
            hits.append(item)
    if not hits:
        words = re.findall(r"[\u4e00-\u9fa5A-Za-z]{2,}", text)
        hits = words[:3]
    return hits[:4]

