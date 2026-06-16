from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from ..models import CaseLibraryDocument

try:  # Optional acceleration for P3 vector retrieval.
    import faiss  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    faiss = None
    np = None

VECTOR_DIM = 512
SYNONYM_MAP = {
    "商业模式": ("盈利模式", "收入模式", "变现"),
    "访谈": ("调研", "问卷", "用户研究"),
    "风险": ("风险控制", "风险管理", "不确定性"),
    "公益": ("社会价值", "公共服务", "非营利"),
    "市场": ("TAM", "SAM", "SOM", "市场规模"),
}


def _tokenize(text: str) -> List[str]:
    raw_words = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text or "")
    words = [w.lower() for w in raw_words]
    # Add Chinese bi-grams to reduce sparse mismatch between short terms.
    for word in raw_words:
        if re.fullmatch(r"[\u4e00-\u9fa5]+", word) and len(word) >= 3:
            for i in range(len(word) - 1):
                words.append(word[i: i + 2])
    return words


def _expand_tokens(tokens: List[str]) -> List[str]:
    expanded = list(tokens)
    for token in tokens:
        for key, synonyms in SYNONYM_MAP.items():
            if token == key or token in key:
                expanded.extend([s.lower() for s in synonyms])
            elif any(token == s.lower() for s in synonyms):
                expanded.append(key.lower())
    return expanded


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for key, val in a.items():
        dot += float(val) * float(b.get(key, 0))
    norm_a = math.sqrt(sum(float(v) ** 2 for v in a.values()))
    norm_b = math.sqrt(sum(float(v) ** 2 for v in b.values()))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _hash_vec(text: str, dim: int = VECTOR_DIM):
    if np is None:
        return None
    vec = np.zeros((dim,), dtype="float32")
    for token in _expand_tokens(_tokenize(text)):
        bucket = hash(token) % dim
        vec[bucket] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return vec


@lru_cache(maxsize=1)
def _build_faiss_index() -> Tuple[Any, List[Dict[str, Any]]]:
    if faiss is None or np is None:
        return None, []

    docs = list(CaseLibraryDocument.objects.filter(clean_status=CaseLibraryDocument.CLEAN_DONE)[:800])
    if not docs:
        return None, []

    vectors = []
    payload = []
    for doc in docs:
        text = f"{doc.title}\n{(doc.extracted_text or '')[:5000]}"
        vec = _hash_vec(text)
        if vec is None:
            continue
        vectors.append(vec)
        payload.append(
            {
                "id": doc.id,
                "title": doc.title,
                "industry": doc.industry_category,
                "summary": (doc.extracted_text or "")[:220],
                "core_facts": doc.core_facts or {},
            }
        )

    if not vectors:
        return None, []

    matrix = np.vstack(vectors).astype("float32")
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(matrix)
    return index, payload


class VectorRetrievalService:
    """Lightweight vector retrieval with cosine over token frequency.

    This keeps runtime dependency-free and can be swapped with FAISS/Milvus later.
    """

    def retrieval_mode(self) -> str:
        return "faiss" if faiss is not None and np is not None else "fallback-cosine"

    def recall_cases_with_meta(self, query: str, top_k: int = 5, industry: str = "") -> Dict[str, Any]:
        rows = self.recall_cases(query=query, top_k=top_k, industry=industry)
        return {
            "query": query,
            "retrieval_mode": self.retrieval_mode(),
            "total": len(rows),
            "items": rows,
        }

    def recall_cases(self, query: str, top_k: int = 5, industry: str = "") -> List[Dict[str, Any]]:
        if faiss is not None and np is not None:
            rows = self._recall_by_faiss(query=query, top_k=top_k, industry=industry)
            if rows:
                return rows

        return self._recall_by_cosine(query=query, top_k=top_k, industry=industry)

    def _recall_by_faiss(self, query: str, top_k: int = 5, industry: str = "") -> List[Dict[str, Any]]:
        index, payload = _build_faiss_index()
        if index is None or not payload or np is None:
            return []

        q = _hash_vec(query)
        if q is None:
            return []
        q = q.reshape(1, -1).astype("float32")
        query_tokens = set(_expand_tokens(_tokenize(query)))

        size = max(1, min(len(payload), int(top_k or 5) * 4))
        scores, indices = index.search(q, size)

        rows: List[Dict[str, Any]] = []
        for idx, score in zip(indices[0].tolist(), scores[0].tolist()):
            if idx < 0 or idx >= len(payload):
                continue
            item = payload[idx]
            if industry and industry not in (item.get("industry") or ""):
                continue
            title_tokens = set(_expand_tokens(_tokenize(item.get("title") or "")))
            overlap = len(query_tokens & title_tokens)
            rerank_score = float(score) + min(0.18, overlap * 0.03)
            rows.append({**item, "score": round(rerank_score, 4)})
            if len(rows) >= max(1, int(top_k or 5)):
                break
        rows.sort(key=lambda x: x.get("score", 0), reverse=True)
        return rows

    def _recall_by_cosine(self, query: str, top_k: int = 5, industry: str = "") -> List[Dict[str, Any]]:
        queryset = CaseLibraryDocument.objects.filter(clean_status=CaseLibraryDocument.CLEAN_DONE)
        if industry:
            queryset = queryset.filter(industry_category__icontains=industry)

        query_vec = Counter(_expand_tokens(_tokenize(query)))
        query_tokens = set(query_vec.keys())
        scored: List[Dict[str, Any]] = []
        for doc in queryset[:400]:
            doc_text = f"{doc.title}\n{doc.extracted_text[:3000]}"
            doc_vec = Counter(_expand_tokens(_tokenize(doc_text)))
            score = _cosine(query_vec, doc_vec)
            # Hybrid rerank: reward title hit and term overlap.
            title_tokens = set(_expand_tokens(_tokenize(doc.title or "")))
            overlap = len(query_tokens & set(doc_vec.keys()))
            title_boost = 0.08 if (query_tokens & title_tokens) else 0.0
            score = round(float(score) + min(0.22, overlap * 0.012) + title_boost, 4)
            if score <= 0:
                continue
            scored.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "industry": doc.industry_category,
                    "score": score,
                    "summary": (doc.extracted_text or "")[:220],
                    "core_facts": doc.core_facts or {},
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: max(1, int(top_k or 5))]

