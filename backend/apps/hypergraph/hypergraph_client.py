from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

Node = Dict[str, object]
Relation = Dict[str, object]
Hyperedge = Dict[str, object]
LlmExtractFn = Callable[[str, Sequence[str], Sequence[str]], Sequence[str]]


class HypergraphClient:
    """Read-only in-memory client for JSON knowledge graph and hypergraph data.

    The client loads three JSON files and builds reusable indexes for fast lookup:
    - `node_by_id`
    - `nodes_by_label`
    - `relations_from`
    - `relations_to`
    - `hyperedges_by_member`
    - `hyperedges_by_type`

    Parameters
    ----------
    kg_nodes_path:
        Path to `kg_nodes.json`.
    kg_relations_path:
        Path to `kg_relations.json`.
    hypergraph_edges_path:
        Path to `hypergraph_edges.json`.
    llm_extract_fn:
        Optional callback used by `extract_entities_from_text`. Signature:
        `(text, known_node_names, known_labels) -> list[str]`.
        Returned strings can be node ids or node names.
    fuzzy_cutoff:
        Similarity threshold (0~1) used by fuzzy name matching.
    """

    def __init__(
        self,
        kg_nodes_path: str | Path,
        kg_relations_path: str | Path,
        hypergraph_edges_path: str | Path,
        llm_extract_fn: Optional[LlmExtractFn] = None,
        fuzzy_cutoff: float = 0.62,
    ) -> None:
        self.kg_nodes_path = Path(kg_nodes_path)
        self.kg_relations_path = Path(kg_relations_path)
        self.hypergraph_edges_path = Path(hypergraph_edges_path)
        self.llm_extract_fn = llm_extract_fn
        self.fuzzy_cutoff = max(0.0, min(1.0, float(fuzzy_cutoff)))

        self.nodes: List[Node] = []
        self.relations: List[Relation] = []
        self.hyperedges: List[Hyperedge] = []

        self.node_by_id: Dict[str, Node] = {}
        self.nodes_by_label: Dict[str, List[Node]] = defaultdict(list)
        self.relations_from: Dict[str, List[Relation]] = defaultdict(list)
        self.relations_to: Dict[str, List[Relation]] = defaultdict(list)
        self.hyperedges_by_member: Dict[str, List[Hyperedge]] = defaultdict(list)
        self.hyperedges_by_type: Dict[str, List[Hyperedge]] = defaultdict(list)

        self._project_ids: Set[str] = set()
        self._name_by_id: Dict[str, str] = {}
        self._names_lower: List[str] = []
        self._name_to_ids: Dict[str, List[str]] = defaultdict(list)
        self._search_pool_by_label: Dict[str, List[tuple[str, str]]] = defaultdict(list)
        self._token_to_node_ids: Dict[str, Set[str]] = defaultdict(set)

        self._load_all()
        self._build_indexes()

    def get_node(self, node_id: str) -> Optional[Node]:
        """Return node dict by node id, or None if not found."""
        return self.node_by_id.get(str(node_id))

    def find_nodes_by_name(self, name: str, label: Optional[str] = None) -> List[str]:
        """Find node ids by fuzzy name matching.

        Matching strategy:
        1. Exact lowercase match
        2. Substring match
        3. difflib close match + SequenceMatcher ranking

        Parameters
        ----------
        name:
            Query text.
        label:
            Optional node label filter (e.g. `Project`, `Market`).

        Returns
        -------
        list[str]
            Matched node ids sorted by descending confidence.
        """
        query = (name or "").strip().lower()
        if not query:
            return []

        if label:
            candidates = self._search_pool_by_label.get(label, [])
        else:
            candidates = [(node_id, name_lower) for node_id, name_lower in self._name_by_id.items()]

        scored = self._score_nodes_for_query(query=query, candidates=candidates, threshold=self.fuzzy_cutoff)
        return [node_id for node_id, _ in scored]

    def _score_nodes_for_query(
        self,
        query: str,
        candidates: Sequence[Tuple[str, str]],
        threshold: float = 0.52,
    ) -> List[Tuple[str, float]]:
        if not query or not candidates:
            return []

        query = (query or "").strip().lower()
        score_map: Dict[str, float] = {}
        query_tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", query)

        for node_id, node_name in candidates:
            score = 0.0
            if node_name == query:
                score = 1.0
            elif query in node_name or node_name in query:
                score = 0.9
            else:
                sim = SequenceMatcher(None, query, node_name).ratio()
                score = max(score, sim)

            if query_tokens:
                token_hits = 0
                for token in query_tokens:
                    if token in node_name:
                        token_hits += 1
                token_ratio = token_hits / float(len(query_tokens))
                score = max(score, min(0.95, 0.45 + token_ratio * 0.55))

            if score >= threshold:
                score_map[node_id] = max(score_map.get(node_id, 0.0), score)

        if not score_map:
            pool_names = [item[1] for item in candidates]
            close_names = set(get_close_matches(query, pool_names, n=24, cutoff=self.fuzzy_cutoff))
            for node_id, node_name in candidates:
                if node_name in close_names:
                    sim = SequenceMatcher(None, query, node_name).ratio()
                    if sim >= threshold:
                        score_map[node_id] = max(score_map.get(node_id, 0.0), sim)

        scored = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
        return scored

    def get_related_hyperedges(
        self,
        node_ids: Iterable[str],
        hyperedge_types: Optional[Iterable[str]] = None,
    ) -> List[Hyperedge]:
        """Return hyperedges connected to any given node ids.

        Parameters
        ----------
        node_ids:
            Node ids to search.
        hyperedge_types:
            Optional hyperedge type whitelist.
        """
        node_id_set = {str(node_id).strip() for node_id in node_ids if str(node_id).strip()}
        if not node_id_set:
            return []

        type_set = {str(t).strip() for t in (hyperedge_types or []) if str(t).strip()}
        result: List[Hyperedge] = []
        seen: Set[str] = set()

        for node_id in node_id_set:
            for edge in self.hyperedges_by_member.get(node_id, []):
                edge_id = str(edge.get("id") or "")
                edge_type = str(edge.get("type") or "")
                if type_set and edge_type not in type_set:
                    continue
                if edge_id and edge_id in seen:
                    continue
                if edge_id:
                    seen.add(edge_id)
                result.append(edge)
        return result

    def get_project_context(self, project_id: str) -> Dict[str, object]:
        """Get one-hop context around a project node.

        Returns project-related nodes, relations, hyperedges and summary stats.
        """
        project_id = str(project_id)
        project = self.get_node(project_id)
        if not project or str(project.get("label") or "") != "Project":
            return {
                "project_id": project_id,
                "project": None,
                "related_nodes": [],
                "relations": [],
                "hyperedges": [],
                "mistakes": [],
                "stats": {"relation_count": 0, "node_count": 0, "hyperedge_count": 0, "mistake_count": 0},
            }

        outgoing = list(self.relations_from.get(project_id, []))
        incoming = list(self.relations_to.get(project_id, []))
        relations = outgoing + incoming

        related_node_ids: Set[str] = {project_id}
        for rel in relations:
            from_id = str(rel.get("from") or "")
            to_id = str(rel.get("to") or "")
            if from_id:
                related_node_ids.add(from_id)
            if to_id:
                related_node_ids.add(to_id)

        related_nodes = [self.node_by_id[node_id] for node_id in related_node_ids if node_id in self.node_by_id]
        hyperedges = self.get_related_hyperedges(related_node_ids)
        mistakes = [node for node in related_nodes if str(node.get("label") or "") == "Mistake"]

        return {
            "project_id": project_id,
            "project": project,
            "related_nodes": related_nodes,
            "relations": relations,
            "hyperedges": hyperedges,
            "mistakes": mistakes,
            "stats": {
                "relation_count": len(relations),
                "node_count": len(related_nodes),
                "hyperedge_count": len(hyperedges),
                "mistake_count": len(mistakes),
            },
        }

    def find_similar_projects(self, project_id: str, top_k: int = 5) -> List[Dict[str, object]]:
        """Find similar projects by shared Market/Technology nodes.

        Similarity is Jaccard score over the union of related Market and Technology ids.
        """
        project_id = str(project_id)
        if project_id not in self._project_ids:
            return []

        seed_features = self._project_feature_nodes(project_id)
        if not seed_features:
            return []

        result: List[Dict[str, object]] = []
        for other_id in self._project_ids:
            if other_id == project_id:
                continue
            other_features = self._project_feature_nodes(other_id)
            if not other_features:
                continue

            inter = seed_features & other_features
            union = seed_features | other_features
            score = len(inter) / float(len(union)) if union else 0.0
            if score <= 0:
                continue

            result.append(
                {
                    "project_id": other_id,
                    "project_name": self._node_name(other_id),
                    "score": round(score, 4),
                    "shared_features": [self._node_name(node_id) for node_id in sorted(inter)],
                }
            )

        result.sort(key=lambda item: item["score"], reverse=True)
        return result[: max(1, int(top_k))]

    def check_consistency(self, project_id: str) -> List[str]:
        """Run rule-based consistency checks and return warning messages."""
        project_id = str(project_id)
        warnings: List[str] = []

        if project_id not in self._project_ids:
            return [f"项目不存在：{project_id}"]

        market_nodes = self._related_market_nodes(project_id)
        tech_nodes = self._related_technology_nodes(project_id)
        method_nodes = self._related_nodes_by_label(project_id, {"Method"})
        metric_nodes = self._related_nodes_by_label(project_id, {"Metric"})
        hyperedges = self.get_related_hyperedges([project_id])
        hyperedge_types = {str(edge.get("type") or "") for edge in hyperedges}

        if not market_nodes:
            warnings.append("缺少 Market 节点：项目目标市场信息不足。")
        if tech_nodes and not ({"ValueLoop", "BusinessModelConsistency"} & hyperedge_types):
            warnings.append("存在 Technology 节点但缺少 ValueLoop 超边：价值闭环证据不足。")
        if not method_nodes:
            warnings.append("缺少 Method 节点：实施路径与验证方法不清晰。")
        if not metric_nodes:
            warnings.append("缺少 Metric 节点：缺乏可量化评价指标。")
        if self._related_nodes_by_label(project_id, {"Mistake"}) and not ({"RiskPattern", "CompetitionScoreMapping"} & hyperedge_types):
            warnings.append("存在 Mistake 节点但缺少 RiskPattern 超边：风险模式未系统化表达。")

        return warnings

    def extract_entities_from_text(self, text: str) -> List[str]:
        """Extract candidate node ids from free text.

        Strategy:
        1. If provided, call external LLM extraction callback.
        2. Fallback to keyword/token matching against node names.
        3. Use fuzzy matching for residual long tokens.
        """
        content = (text or "").strip()
        if not content:
            return []

        score_map: Dict[str, float] = defaultdict(float)

        if self.llm_extract_fn is not None:
            try:
                llm_items = self.llm_extract_fn(content, list(self._name_to_ids.keys()), list(self.nodes_by_label.keys()))
            except Exception:
                llm_items = []
            for item in llm_items or []:
                token = str(item or "").strip()
                if not token:
                    continue
                if token in self.node_by_id:
                    score_map[token] = max(score_map.get(token, 0.0), 1.0)
                    continue
                for node_id, score in self._score_nodes_for_query(
                    query=token,
                    candidates=[(nid, name) for nid, name in self._name_by_id.items()],
                    threshold=0.52,
                )[:12]:
                    score_map[node_id] = max(score_map.get(node_id, 0.0), min(0.98, score + 0.05))

        lowered = content.lower()
        for token, node_ids in self._token_to_node_ids.items():
            if len(token) < 2:
                continue
            if token in lowered:
                boost = 0.55 if len(token) <= 3 else 0.68
                for node_id in node_ids:
                    score_map[node_id] = max(score_map.get(node_id, 0.0), boost)

        rough_tokens = set(re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", content))
        for token in rough_tokens:
            candidates = self._score_nodes_for_query(
                query=token,
                candidates=[(nid, name) for nid, name in self._name_by_id.items()],
                threshold=0.55,
            )
            for node_id, score in candidates[:8]:
                score_map[node_id] = max(score_map.get(node_id, 0.0), score)

        ordered = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
        return [node_id for node_id, score in ordered if score >= 0.5][:120]

    def diagnose_project(self, text_or_id: str) -> Dict[str, object]:
        """Generate a lightweight diagnostic report from a project id or project text."""
        value = str(text_or_id or "").strip()
        if not value:
            return {
                "enabled": False,
                "input_type": "empty",
                "matched_project": None,
                "matched_project_node_id": None,
                "matched_project_name": None,
                "consistency_alerts": ["输入为空"],
                "missing_node_labels": ["Project", "Market", "Technology", "Method", "Metric"],
                "risk_patterns": [],
                "provenance": {"node_sources": [], "hyperedge_evidence": []},
                "warnings": ["输入为空"],
                "missing_key_nodes": ["Project", "Market", "Technology", "Method", "Metric"],
                "matched_entity_ids": [],
                "potential_risk_patterns": [],
                "suggested_evidence": [],
                "similar_projects": [],
            }

        if value in self._project_ids:
            project_id = value
            context = self.get_project_context(project_id)
            related_ids = [str(node.get("id") or "") for node in context.get("related_nodes") or []]
            risk_patterns = self.get_related_hyperedges([project_id] + related_ids, hyperedge_types=["RiskPattern"])
            suggestions = self._collect_evidence_snippets(risk_patterns)
            warnings = self.check_consistency(project_id)
            missing = self._missing_key_nodes(project_id)
            similar_rows = self._normalize_similar_projects(self.find_similar_projects(project_id, top_k=5))
            normalized_risk_patterns = self._normalize_risk_patterns(risk_patterns)
            project_name = self._node_name(project_id)
            matched_labels = sorted(
                {
                    str((self.get_node(node_id) or {}).get("label") or "")
                    for node_id in related_ids
                    if str((self.get_node(node_id) or {}).get("label") or "")
                }
            )
            return {
                "enabled": True,
                "input_type": "project_id",
                "matched_project": {"id": project_id, "name": project_name},
                "matched_project_node_id": project_id,
                "matched_project_name": project_name,
                "consistency_alerts": warnings,
                "missing_node_labels": missing,
                "risk_patterns": normalized_risk_patterns,
                "provenance": {"node_sources": [], "hyperedge_evidence": []},
                "project_id": project_id,
                "project_name": project_name,
                "warnings": warnings,
                "missing_key_nodes": missing,
                "matched_entity_ids": related_ids,
                "potential_risk_patterns": risk_patterns,
                "suggested_evidence": suggestions,
                "similar_projects": similar_rows,
                "entity_match_stats": {
                    "matched_entity_count": len(related_ids),
                    "matched_labels": matched_labels,
                    "project_confidence": 1.0,
                },
            }

        matched_entity_ids = self.extract_entities_from_text(value)
        guessed_project_id, project_confidence = self._infer_project_candidate(value, matched_entity_ids)
        if guessed_project_id and guessed_project_id not in matched_entity_ids:
            matched_entity_ids = [guessed_project_id, *matched_entity_ids]

        matched_hyperedges = self.get_related_hyperedges(matched_entity_ids)
        risk_patterns = [edge for edge in matched_hyperedges if str(edge.get("type") or "") == "RiskPattern"]

        similar_rows: List[Dict[str, object]] = []
        if guessed_project_id:
            similar_rows = self._normalize_similar_projects(self.find_similar_projects(guessed_project_id, top_k=5))

        missing = self._missing_key_labels_from_entities(matched_entity_ids)
        guessed_project_name = self._node_name(guessed_project_id) if guessed_project_id else None
        warnings = []
        if guessed_project_id:
            warnings = self.check_consistency(guessed_project_id)
        if not warnings:
            warnings = ["当前输入为文本匹配诊断，建议绑定项目标题可提升命中率。"]
        matched_labels = sorted(
            {
                str((self.get_node(node_id) or {}).get("label") or "")
                for node_id in matched_entity_ids
                if str((self.get_node(node_id) or {}).get("label") or "")
            }
        )
        return {
            "enabled": True,
            "input_type": "text",
            "matched_project": {"id": guessed_project_id, "name": guessed_project_name} if guessed_project_id else None,
            "matched_project_node_id": guessed_project_id,
            "matched_project_name": guessed_project_name,
            "consistency_alerts": warnings,
            "missing_node_labels": missing,
            "risk_patterns": self._normalize_risk_patterns(risk_patterns),
            "provenance": {"node_sources": [], "hyperedge_evidence": []},
            "project_id": guessed_project_id,
            "project_name": guessed_project_name,
            "warnings": warnings,
            "missing_key_nodes": missing,
            "matched_entity_ids": matched_entity_ids,
            "potential_risk_patterns": risk_patterns,
            "suggested_evidence": self._collect_evidence_snippets(matched_hyperedges),
            "similar_projects": similar_rows,
            "entity_match_stats": {
                "matched_entity_count": len(matched_entity_ids),
                "matched_labels": matched_labels,
                "project_confidence": project_confidence,
            },
        }

    def get_competition_resources(self, competition_name: str) -> Dict[str, object]:
        """Return resource nodes for a competition and related projects."""
        query = (competition_name or "").strip().lower()
        if not query:
            return {"resources": [], "projects": []}

        resources: List[Node] = []
        resource_ids: Set[str] = set()
        for node in self.nodes_by_label.get("Resource", []):
            props = node.get("properties") or {}
            name = str(props.get("name") or "").lower()
            provider = str(props.get("provider") or "").lower()
            node_type = str(props.get("type") or "").lower()
            if query in name or query in provider or query in node_type:
                resources.append(node)
                resource_ids.add(str(node.get("id") or ""))

        project_ids: Set[str] = set()
        for resource_id in resource_ids:
            for rel in self.relations_to.get(resource_id, []):
                from_id = str(rel.get("from") or "")
                if from_id in self._project_ids:
                    project_ids.add(from_id)
            for rel in self.relations_from.get(resource_id, []):
                to_id = str(rel.get("to") or "")
                if to_id in self._project_ids:
                    project_ids.add(to_id)

        projects = [self.node_by_id[project_id] for project_id in sorted(project_ids)]
        return {"resources": resources, "projects": projects}

    def get_common_mistakes(self, top_k: int = 10) -> List[Dict[str, object]]:
        """Return most frequent Mistake nodes counted by `EXEMPLIFIES_MISTAKE` relations."""
        counter: Dict[str, int] = defaultdict(int)
        for rel in self.relations:
            if str(rel.get("type") or "") != "EXEMPLIFIES_MISTAKE":
                continue
            target_id = str(rel.get("to") or "")
            node = self.get_node(target_id)
            if node and str(node.get("label") or "") == "Mistake":
                counter[target_id] += 1

        rows = [
            {
                "mistake_id": node_id,
                "mistake_name": self._node_name(node_id),
                "count": count,
            }
            for node_id, count in counter.items()
        ]
        rows.sort(key=lambda item: item["count"], reverse=True)
        return rows[: max(1, int(top_k))]

    def _load_all(self) -> None:
        self.nodes = self._load_json_array(self.kg_nodes_path, top_key="nodes")
        self.relations = self._load_json_array(self.kg_relations_path, top_key="relations")
        self.hyperedges = self._load_json_array(self.hypergraph_edges_path, top_key="hyperedges")

    def _build_indexes(self) -> None:
        for node in self.nodes:
            node_id = str(node.get("id") or "").strip()
            if not node_id:
                continue
            self.node_by_id[node_id] = node
            label = str(node.get("label") or "Unknown").strip() or "Unknown"
            self.nodes_by_label[label].append(node)
            name_lower = self._node_name(node_id).lower()
            self._name_by_id[node_id] = name_lower
            self._name_to_ids[name_lower].append(node_id)
            self._search_pool_by_label[label].append((node_id, name_lower))
            self._index_name_tokens(name_lower, node_id)
            if label == "Project":
                self._project_ids.add(node_id)

        self._names_lower = list(self._name_to_ids.keys())

        for rel in self.relations:
            from_id = str(rel.get("from") or "").strip()
            to_id = str(rel.get("to") or "").strip()
            if from_id:
                self.relations_from[from_id].append(rel)
            if to_id:
                self.relations_to[to_id].append(rel)

        for edge in self.hyperedges:
            edge_type = str(edge.get("type") or "Unknown").strip() or "Unknown"
            self.hyperedges_by_type[edge_type].append(edge)
            members = edge.get("member_node_ids") or []
            for member_id in members:
                key = str(member_id).strip()
                if key:
                    self.hyperedges_by_member[key].append(edge)

    def _index_name_tokens(self, name_lower: str, node_id: str) -> None:
        for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", name_lower):
            self._token_to_node_ids[token].add(node_id)

    def _infer_project_candidate(self, text: str, matched_entity_ids: Sequence[str]) -> Tuple[Optional[str], float]:
        scores: Dict[str, float] = defaultdict(float)
        for node_id in matched_entity_ids:
            node = self.get_node(node_id) or {}
            if str(node.get("label") or "") == "Project":
                scores[node_id] += 0.85

            for rel in self.relations_from.get(node_id, []):
                to_id = str(rel.get("to") or "")
                if to_id in self._project_ids:
                    scores[to_id] += 0.35
            for rel in self.relations_to.get(node_id, []):
                from_id = str(rel.get("from") or "")
                if from_id in self._project_ids:
                    scores[from_id] += 0.35

        short_query = str(text or "").strip()[:160]
        if short_query:
            project_candidates = self._search_pool_by_label.get("Project", [])
            for project_id, score in self._score_nodes_for_query(short_query, project_candidates, threshold=0.45)[:18]:
                scores[project_id] += score * 1.2

        if not scores:
            return None, 0.0
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_id, best_score = ordered[0]
        confidence = round(min(1.0, float(best_score) / 1.8), 4)
        return best_id, confidence

    def _missing_key_labels_from_entities(self, node_ids: Sequence[str]) -> List[str]:
        checks = {
            "Project": False,
            "Market": False,
            "Technology": False,
            "Method": False,
            "Metric": False,
        }
        for node_id in node_ids:
            node = self.get_node(node_id)
            if not node:
                continue
            label = str(node.get("label") or "")
            if label == "Project":
                checks["Project"] = True
            if label == "Method":
                checks["Method"] = True
            if label == "Metric":
                checks["Metric"] = True
            if self._is_market_like(node):
                checks["Market"] = True
            if self._is_technology_like(node):
                checks["Technology"] = True
        return [name for name, ok in checks.items() if not ok]

    def _project_feature_nodes(self, project_id: str) -> Set[str]:
        features: Set[str] = set()
        for node in self._related_nodes_by_filter(project_id, lambda n: self._is_market_like(n) or self._is_technology_like(n)):
            node_id = str(node.get("id") or "")
            if node_id:
                features.add(node_id)

        return features

    def _is_market_like(self, node: Optional[Node]) -> bool:
        if not node:
            return False
        label = str(node.get("label") or "")
        if label == "Market":
            return True
        if label != "Concept":
            return False
        props = node.get("properties") or {}
        concept_type = str(props.get("concept_type") or "").lower()
        name = str(props.get("name") or node.get("id") or "").lower()
        if concept_type in {"market", "tam_sam_som", "customer", "segment"}:
            return True
        return any(token in name for token in ["tam", "sam", "som", "市场", "客群", "用户", "需求"])

    def _is_technology_like(self, node: Optional[Node]) -> bool:
        if not node:
            return False
        label = str(node.get("label") or "")
        if label == "Technology":
            return True
        if label != "Concept":
            return False
        props = node.get("properties") or {}
        concept_type = str(props.get("concept_type") or "").lower()
        name = str(props.get("name") or node.get("id") or "").lower()
        if concept_type in {"technology", "tech", "algorithm", "model"}:
            return True
        return any(token in name for token in ["技术", "算法", "模型", "系统", "芯片", "识别", "检测", "平台"])

    def _related_nodes_by_filter(self, project_id: str, predicate) -> List[Node]:
        node_ids: Set[str] = set()
        for rel in self.relations_from.get(project_id, []):
            node_id = str(rel.get("to") or "")
            node = self.get_node(node_id)
            if node and predicate(node):
                node_ids.add(node_id)
        for rel in self.relations_to.get(project_id, []):
            node_id = str(rel.get("from") or "")
            node = self.get_node(node_id)
            if node and predicate(node):
                node_ids.add(node_id)
        return [self.node_by_id[node_id] for node_id in sorted(node_ids) if node_id in self.node_by_id]

    def _related_market_nodes(self, project_id: str) -> List[Node]:
        return self._related_nodes_by_filter(project_id, self._is_market_like)

    def _related_technology_nodes(self, project_id: str) -> List[Node]:
        return self._related_nodes_by_filter(project_id, self._is_technology_like)

    def _related_nodes_by_label(self, project_id: str, labels: Set[str]) -> List[Node]:
        labels = set(labels)
        node_ids: Set[str] = set()
        for rel in self.relations_from.get(project_id, []):
            node_id = str(rel.get("to") or "")
            node = self.get_node(node_id)
            if node and str(node.get("label") or "") in labels:
                node_ids.add(node_id)
        for rel in self.relations_to.get(project_id, []):
            node_id = str(rel.get("from") or "")
            node = self.get_node(node_id)
            if node and str(node.get("label") or "") in labels:
                node_ids.add(node_id)
        return [self.node_by_id[node_id] for node_id in sorted(node_ids)]

    def _missing_key_nodes(self, project_id: str) -> List[str]:
        missing: List[str] = []
        if not self._related_market_nodes(project_id):
            missing.append("Market")
        if not self._related_technology_nodes(project_id):
            missing.append("Technology")
        if not self._related_nodes_by_label(project_id, {"Method"}):
            missing.append("Method")
        if not self._related_nodes_by_label(project_id, {"Metric"}):
            missing.append("Metric")
        return missing

    def _collect_evidence_snippets(self, hyperedges: Sequence[Hyperedge]) -> List[str]:
        snippets: List[str] = []
        for edge in hyperedges:
            props = edge.get("properties") or {}
            evidence = props.get("evidence")
            if isinstance(evidence, list):
                for item in evidence:
                    text = str(item).strip()
                    if text:
                        snippets.append(text)
            elif evidence:
                snippets.append(str(evidence).strip())
        return snippets[:8]

    def _normalize_similar_projects(self, rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
        normalized: List[Dict[str, object]] = []
        for item in rows:
            project_id = str(item.get("project_id") or "").strip()
            if not project_id:
                continue
            score = item.get("score")
            try:
                similarity = float(score)
            except Exception:
                similarity = 0.0
            normalized.append(
                {
                    "id": project_id,
                    "name": str(item.get("project_name") or self._node_name(project_id)),
                    "similarity_score": round(similarity, 4),
                    "shared_features": item.get("shared_features") or [],
                }
            )
        return normalized

    def _normalize_risk_patterns(self, hyperedges: Sequence[Hyperedge]) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        seen: Set[tuple[str, str]] = set()
        for edge in hyperedges:
            members = [str(item).strip() for item in (edge.get("member_node_ids") or []) if str(item).strip()]
            mistake_names = [self._node_name(node_id) for node_id in members if str((self.get_node(node_id) or {}).get("label") or "") == "Mistake"]
            risk_type = (mistake_names[0] if mistake_names else "潜在风险模式")[:80]
            severity = self._risk_severity(risk_type)
            example = self._risk_example(edge)
            key = (risk_type, example)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"type": risk_type, "severity": severity, "example": example})
        return rows[:8]

    def _risk_example(self, edge: Hyperedge) -> str:
        props = edge.get("properties") or {}
        evidence = props.get("evidence")
        if isinstance(evidence, dict):
            text = str(evidence.get("text") or "").strip()
            if text:
                return text[:120]
        if isinstance(evidence, list):
            for item in evidence:
                text = str(item).strip()
                if text:
                    return text[:120]
        if evidence:
            text = str(evidence).strip()
            if text:
                return text[:120]
        return "历史样本显示该风险模式可能影响项目落地。"

    @staticmethod
    def _risk_severity(risk_text: str) -> str:
        text = str(risk_text or "").lower()
        if any(keyword in text for keyword in ["严重", "失败", "断裂", "过高", "不可行"]):
            return "高"
        if any(keyword in text for keyword in ["不足", "不清晰", "失衡", "缺失", "偏低"]):
            return "中"
        return "中"

    def _node_name(self, node_id: str) -> str:
        node = self.node_by_id.get(str(node_id))
        if not node:
            return str(node_id)
        props = node.get("properties") or {}
        return str(props.get("name") or node.get("id") or node_id)

    @staticmethod
    def _load_json_array(path: Path, top_key: str) -> List[Dict[str, object]]:
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
        with path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp) or {}
        if isinstance(payload, dict):
            items = payload.get(top_key) or []
            if isinstance(items, list):
                return items
            return []
        if isinstance(payload, list):
            return payload
        return []

