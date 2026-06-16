from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings

from ...hypergraph import HypergraphClient
from ..models import Plan
from .graph_observability import track_graph_call

GRAPH_FILE_SET_PRIORITY: tuple[tuple[str, str, str, str], ...] = (
    ("legacy", "kg_nodes.json", "kg_relations.json", "hypergraph_edges.json"),
    ("v1v2", "kg_nodes_v1v2.json", "kg_relations_v1v2.json", "hypergraph_edges_v1v2.json"),
)
_CACHED_CLIENT: Optional[HypergraphClient] = None
_CACHED_SIGNATURE: str = ""


def _graph_data_candidates() -> List[Path]:
    roots: List[Path] = []
    configured = str(os.getenv("GRAPH_DATA_DIR") or "").strip()
    if configured:
        roots.append(Path(configured).expanduser())
    roots.extend(
        [
            Path(settings.BASE_DIR).parent,
            Path(settings.BASE_DIR),
            Path(settings.BASE_DIR) / "data",
        ]
    )

    deduped: List[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return deduped


def _iter_graph_file_sets():
    for root in _graph_data_candidates():
        ranked_sets = []
        for priority, (dataset, nodes_name, relations_name, hyperedges_name) in enumerate(GRAPH_FILE_SET_PRIORITY):
            nodes_path = root / nodes_name
            relations_path = root / relations_name
            hyperedges_path = root / hyperedges_name
            if not (nodes_path.exists() and relations_path.exists() and hyperedges_path.exists()):
                continue
            freshness = max(
                int(nodes_path.stat().st_mtime_ns),
                int(relations_path.stat().st_mtime_ns),
                int(hyperedges_path.stat().st_mtime_ns),
            )
            ranked_sets.append((int(freshness), -int(priority), dataset, nodes_path, relations_path, hyperedges_path))
        ranked_sets.sort(reverse=True)
        for _, _, dataset, nodes_path, relations_path, hyperedges_path in ranked_sets:
            yield dataset, nodes_path, relations_path, hyperedges_path


def _file_signature(nodes_path: Path, relations_path: Path, hyperedges_path: Path) -> str:
    return "|".join(
        [
            str(nodes_path.resolve()),
            str(relations_path.resolve()),
            str(hyperedges_path.resolve()),
            str(nodes_path.stat().st_mtime_ns),
            str(relations_path.stat().st_mtime_ns),
            str(hyperedges_path.stat().st_mtime_ns),
        ]
    )


def _safe_text(value: Any, limit: int = 220) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _normalize_sources(raw: Any, node_id: str, node_label: str, node_name: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        iterable = raw
    elif isinstance(raw, dict):
        iterable = [raw]
    elif raw:
        iterable = [{"text": str(raw)}]
    else:
        iterable = []

    for item in iterable:
        if isinstance(item, dict):
            rows.append(
                {
                    "kind": "node_source",
                    "node_id": node_id,
                    "node_label": node_label,
                    "node_name": node_name,
                    "file": _safe_text(item.get("file"), 260),
                    "text": _safe_text(item.get("text"), 260),
                    "competition": _safe_text(item.get("competition"), 80),
                }
            )
        else:
            rows.append(
                {
                    "kind": "node_source",
                    "node_id": node_id,
                    "node_label": node_label,
                    "node_name": node_name,
                    "file": "",
                    "text": _safe_text(item, 260),
                    "competition": "",
                }
            )
    return rows


def _node_sources(client: HypergraphClient, node_ids: List[str], limit: int = 24) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    for node_id in node_ids:
        node = client.get_node(node_id) or {}
        label = _safe_text(node.get("label"), 40)
        props = node.get("properties") or {}
        name = _safe_text(props.get("name") or node.get("id"), 120)
        for src in _normalize_sources(props.get("source"), node_id=node_id, node_label=label, node_name=name):
            key = (src.get("node_id"), src.get("file"), src.get("text"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(src)
            if len(rows) >= limit:
                return rows
    return rows


def _hyperedge_evidence(hyperedges: List[Dict[str, Any]], limit: int = 16) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    for edge in hyperedges:
        edge_id = _safe_text(edge.get("id"), 80)
        edge_type = _safe_text(edge.get("type"), 80)
        props = edge.get("properties") or {}
        evidence = props.get("evidence")

        candidates: List[str] = []
        if isinstance(evidence, list):
            candidates = [str(item) for item in evidence if str(item or "").strip()]
        elif isinstance(evidence, dict):
            candidates = [str(evidence)]
        elif evidence:
            candidates = [str(evidence)]

        for text in candidates:
            clean = _safe_text(text, 260)
            key = (edge_id, clean)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "kind": "hyperedge_evidence",
                    "hyperedge_id": edge_id,
                    "hyperedge_type": edge_type,
                    "text": clean,
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def _normalize_similar_projects(rows: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in (rows or []):
        if not isinstance(item, dict):
            text = str(item or "").strip()
            if not text:
                continue
            normalized.append({"id": text, "name": text, "similarity_score": 0.0})
            continue
        project_id = str(item.get("id") or item.get("project_id") or "").strip()
        if not project_id:
            continue
        score = item.get("similarity_score", item.get("score", 0))
        try:
            similarity = float(score)
        except Exception:
            similarity = 0.0
        normalized.append(
            {
                "id": project_id,
                "name": str(item.get("name") or item.get("project_name") or "").strip() or project_id,
                "similarity_score": round(similarity, 4),
            }
        )
    return normalized


def _normalize_risk_patterns(rows: Any) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in (rows or []):
        if not isinstance(item, dict):
            text = str(item or "").strip()
            if not text:
                continue
            normalized.append({"type": text, "severity": "中", "example": "历史样本显示该风险模式可能影响项目落地。"})
            continue
        risk_type = str(item.get("type") or "").strip()
        if not risk_type:
            continue
        severity = str(item.get("severity") or "中").strip() or "中"
        example = str(item.get("example") or "").strip() or "历史样本显示该风险模式可能影响项目落地。"
        normalized.append({"type": risk_type, "severity": severity, "example": example})
    return normalized


def _dedupe_keep_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_diagnosis_report(raw_report: Dict[str, Any], project_node_id: Optional[str], node_sources: List[Dict[str, Any]], edge_evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    report = raw_report or {}
    input_type = str(report.get("input_type") or "none")

    matched = report.get("matched_project") if isinstance(report.get("matched_project"), dict) else {}
    matched_id = (
        str((matched or {}).get("id") or "").strip()
        or str(report.get("matched_project_node_id") or "").strip()
        or str(report.get("project_id") or "").strip()
        or str(project_node_id or "").strip()
    )
    matched_name = (
        str((matched or {}).get("name") or "").strip()
        or str(report.get("matched_project_name") or "").strip()
        or str(report.get("project_name") or "").strip()
    )

    consistency_alerts = report.get("consistency_alerts")
    if not isinstance(consistency_alerts, list):
        consistency_alerts = report.get("warnings") or []

    missing_node_labels = report.get("missing_node_labels")
    if not isinstance(missing_node_labels, list):
        missing_node_labels = report.get("missing_key_nodes") or []

    similar_projects = _normalize_similar_projects(report.get("similar_projects") or [])
    risk_patterns = _normalize_risk_patterns(report.get("risk_patterns") or [])

    return {
        "enabled": bool(report.get("enabled", True)),
        "input_type": input_type,
        "matched_project": {"id": matched_id, "name": matched_name} if matched_id else None,
        "matched_project_node_id": matched_id or None,
        "matched_project_name": matched_name or None,
        "resolved_project_node_id": project_node_id,
        "consistency_alerts": consistency_alerts,
        "missing_node_labels": missing_node_labels,
        "similar_projects": similar_projects,
        "risk_patterns": risk_patterns,
        "suggested_evidence": report.get("suggested_evidence") or [],
        "matched_entity_ids": report.get("matched_entity_ids") or [],
        "entity_match_stats": report.get("entity_match_stats") or {},
        "provenance": {
            "node_sources": node_sources,
            "hyperedge_evidence": edge_evidence,
        },
        # Backward compatibility for existing prompt/rendering paths.
        "warnings": consistency_alerts,
        "missing_key_nodes": missing_node_labels,
        "potential_risk_patterns": report.get("potential_risk_patterns") or [],
    }


def get_hypergraph_client() -> Optional[HypergraphClient]:
    """Return HypergraphClient and auto-refresh when graph files change."""
    global _CACHED_CLIENT, _CACHED_SIGNATURE
    for _dataset, nodes_path, relations_path, hyperedges_path in _iter_graph_file_sets():
        if not (nodes_path.exists() and relations_path.exists() and hyperedges_path.exists()):
            continue
        signature = _file_signature(nodes_path, relations_path, hyperedges_path)
        if _CACHED_CLIENT is not None and signature == _CACHED_SIGNATURE:
            return _CACHED_CLIENT
        try:
            _CACHED_CLIENT = HypergraphClient(
                kg_nodes_path=nodes_path,
                kg_relations_path=relations_path,
                hypergraph_edges_path=hyperedges_path,
            )
            _CACHED_SIGNATURE = signature
            return _CACHED_CLIENT
        except Exception:
            continue
    _CACHED_CLIENT = None
    _CACHED_SIGNATURE = ""
    return None


def resolve_project_node_id(plan: Plan, client: Optional[HypergraphClient] = None) -> Optional[str]:
    """Resolve KG project node id from title first, then from text semantic hints."""
    client = client or get_hypergraph_client()
    if not client:
        return None

    candidates = client.find_nodes_by_name(plan.title or "", label="Project")
    if candidates:
        return candidates[0]
    return _resolve_project_node_id_from_text(plan, client)


def _resolve_project_node_id_from_text(plan: Plan, client: HypergraphClient) -> Optional[str]:
    text = (plan.extracted_text or "").strip()
    if not text and not (plan.title or "").strip():
        return None

    title_hint = (plan.title or "").strip()[:120]
    candidates = []
    if title_hint:
        candidates.extend(client.find_nodes_by_name(title_hint, label="Project")[:8])
    if text:
        candidates.extend(client.extract_entities_from_text(text[:2200])[:80])

    project_scores: Dict[str, float] = {}
    for node_id in candidates:
        node = client.get_node(node_id) or {}
        if str(node.get("label") or "") != "Project":
            # Promote project neighbors when non-project entities are matched.
            for rel in client.relations_from.get(str(node_id), []):
                to_id = str(rel.get("to") or "")
                target = client.get_node(to_id) or {}
                if str(target.get("label") or "") == "Project":
                    project_scores[to_id] = max(project_scores.get(to_id, 0.0), 0.45)
            for rel in client.relations_to.get(str(node_id), []):
                from_id = str(rel.get("from") or "")
                target = client.get_node(from_id) or {}
                if str(target.get("label") or "") == "Project":
                    project_scores[from_id] = max(project_scores.get(from_id, 0.0), 0.45)
            continue
        project_scores[str(node_id)] = max(project_scores.get(str(node_id), 0.0), 0.6)

    if title_hint:
        title_projects = client.find_nodes_by_name(title_hint, label="Project")[:12]
        for idx, node_id in enumerate(title_projects):
            boost = max(0.35, 0.9 - idx * 0.08)
            project_scores[node_id] = max(project_scores.get(node_id, 0.0), boost)

    if not project_scores:
        return None
    ranked = sorted(project_scores.items(), key=lambda item: item[1], reverse=True)
    return ranked[0][0]


def _diagnosis_metrics(report: Dict[str, Any], matched_ids: List[str], node_sources: List[Dict[str, Any]], edge_evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing_count = len(report.get("missing_node_labels") or [])
    expected_labels = 5
    label_coverage = round(max(0.0, min(100.0, ((expected_labels - missing_count) / expected_labels) * 100)), 2)

    matched_entity_count = len({str(item) for item in matched_ids if str(item).strip()})
    source_hit_rate = round(min(100.0, (len(node_sources) / max(matched_entity_count, 1)) * 100), 2)
    provenance_count = len(node_sources) + len(edge_evidence)
    explainability_item_rate = round(min(100.0, (provenance_count / max(matched_entity_count + len(edge_evidence), 1)) * 100), 2)
    project_confidence = float(((report.get("entity_match_stats") or {}).get("project_confidence") or 0) * 100)

    return {
        "matched_entity_count": matched_entity_count,
        "node_source_count": len(node_sources),
        "hyperedge_evidence_count": len(edge_evidence),
        "label_coverage_rate": label_coverage,
        "source_hit_rate": source_hit_rate,
        "explainability_item_rate": explainability_item_rate,
        "project_confidence_rate": round(min(100.0, max(0.0, project_confidence)), 2),
    }


def _diagnosis_outline(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    matched = report.get("matched_project") or {}
    project_name = str(matched.get("name") or matched.get("id") or "未匹配项目")
    alerts = (report.get("consistency_alerts") or [])[:4]
    missing = (report.get("missing_node_labels") or [])[:4]
    risks = (report.get("risk_patterns") or [])[:4]
    suggestions = (report.get("suggested_evidence") or [])[:4]
    metrics = report.get("metrics") or {}

    risk_lines = []
    for row in risks:
        risk_lines.append(
            f"{str(row.get('type') or '潜在风险')}（{str(row.get('severity') or '中')}）"
        )

    return [
        {
            "section": "核心结论",
            "items": [
                f"已匹配项目：{project_name}",
                f"关键标签覆盖率：{metrics.get('label_coverage_rate', 0)}%",
                f"溯源可解释项覆盖：{metrics.get('explainability_item_rate', 0)}%",
            ],
        },
        {
            "section": "一致性缺口",
            "items": alerts or ["暂未发现明显结构冲突"],
        },
        {
            "section": "待补齐节点",
            "items": [f"建议补齐：{item}" for item in missing] or ["关键节点覆盖较完整"],
        },
        {
            "section": "风险模式",
            "items": risk_lines or ["暂未识别到高风险模式"],
        },
        {
            "section": "证据建议",
            "items": suggestions or ["建议补充访谈证据、市场数据、财务假设来源"],
        },
    ]


def build_plan_diagnosis(plan: Plan, client: Optional[HypergraphClient] = None) -> Dict[str, Any]:
    """Build hypergraph diagnosis for a Plan using project id when possible.

    Falls back to text diagnosis when project node id cannot be resolved.
    """
    client = client or get_hypergraph_client()
    if not client:
        track_graph_call(
            graph_type="hypergraph",
            operation="build_plan_diagnosis",
            source="review_runtime",
            success=False,
            user_id=getattr(plan, "student_id", None),
            plan_id=getattr(plan, "id", None),
            detail={"reason": "client_unavailable"},
        )
        return {
            "enabled": False,
            "input_type": "none",
            "matched_project": None,
            "matched_project_node_id": None,
            "matched_project_name": None,
            "resolved_project_node_id": None,
            "consistency_alerts": [],
            "missing_node_labels": [],
            "risk_patterns": [],
            "suggested_evidence": [],
            "matched_entity_ids": [],
            "similar_projects": [],
            "warnings": [],
            "missing_key_nodes": [],
            "potential_risk_patterns": [],
            "entity_match_stats": {},
            "metrics": {
                "matched_entity_count": 0,
                "node_source_count": 0,
                "hyperedge_evidence_count": 0,
                "label_coverage_rate": 0.0,
                "source_hit_rate": 0.0,
                "explainability_item_rate": 0.0,
                "project_confidence_rate": 0.0,
            },
            "diagnosis_outline": [],
            "provenance": {"node_sources": [], "hyperedge_evidence": []},
        }

    project_node_id = resolve_project_node_id(plan, client=client)
    if project_node_id:
        report = client.diagnose_project(project_node_id)
    else:
        text = (plan.extracted_text or "").strip()
        report = client.diagnose_project(text[:3500] if text else (plan.title or ""))

    matched_ids = [str(item) for item in (report.get("matched_entity_ids") or []) if str(item).strip()]
    matched_project_id = str(report.get("matched_project_node_id") or report.get("project_id") or "").strip()
    if matched_project_id and matched_project_id not in matched_ids:
        matched_ids.append(matched_project_id)

    # Add text-level entity matches to improve hit rate when title and graph naming differ.
    extracted_text = (plan.extracted_text or "").strip()
    if extracted_text:
        text_matches = client.extract_entities_from_text(extracted_text[:4800])
        for node_id in text_matches:
            nid = str(node_id).strip()
            if nid and nid not in matched_ids:
                matched_ids.append(nid)

    # Expand around the matched project neighborhood to improve hit rate and explainability.
    pivot_project_id = matched_project_id or str(project_node_id or "").strip()
    if pivot_project_id:
        context = client.get_project_context(pivot_project_id) or {}
        neighbor_ids = [str((row or {}).get("id") or "").strip() for row in (context.get("related_nodes") or [])]
        matched_ids.extend(neighbor_ids[:120])
    matched_ids = _dedupe_keep_order(matched_ids)[:220]

    node_sources = _node_sources(client, matched_ids, limit=72)
    risk_edges = report.get("potential_risk_patterns") or []
    if not risk_edges:
        risk_edges = client.get_related_hyperedges(matched_ids, hyperedge_types=["RiskPattern"])
    if len(risk_edges) < 8:
        risk_edges.extend(
            client.get_related_hyperedges(
                matched_ids,
                hyperedge_types=["ValueLoop", "ResourceLeverage", "EvidenceChain"],
            )
        )

    edge_map: Dict[str, Dict[str, Any]] = {}
    for edge in risk_edges:
        edge_id = str((edge or {}).get("id") or "").strip()
        if not edge_id or edge_id in edge_map:
            continue
        edge_map[edge_id] = edge
    edge_evidence = _hyperedge_evidence(list(edge_map.values()), limit=40)

    report = normalize_diagnosis_report(
        raw_report={**report, "enabled": True},
        project_node_id=project_node_id,
        node_sources=node_sources,
        edge_evidence=edge_evidence,
    )
    report["metrics"] = _diagnosis_metrics(report, matched_ids=matched_ids, node_sources=node_sources, edge_evidence=edge_evidence)
    report["diagnosis_outline"] = _diagnosis_outline(report)

    track_graph_call(
        graph_type="hypergraph",
        operation="build_plan_diagnosis",
        source="review_runtime",
        success=True,
        user_id=getattr(plan, "student_id", None),
        plan_id=getattr(plan, "id", None),
        detail={
            "input_type": report.get("input_type"),
            "resolved_project_node_id": project_node_id,
            "matched_entity_count": len(matched_ids),
            "node_source_count": len(node_sources),
            "hyperedge_evidence_count": len(edge_evidence),
            "label_coverage_rate": (report.get("metrics") or {}).get("label_coverage_rate"),
            "explainability_item_rate": (report.get("metrics") or {}).get("explainability_item_rate"),
        },
    )
    return report


def build_plan_rubric_basis(plan: Plan, client: Optional[HypergraphClient] = None) -> Dict[str, Any]:
    """Build rubric evidence basis from hypergraph context for the given plan."""
    client = client or get_hypergraph_client()
    if not client:
        track_graph_call(
            graph_type="hypergraph",
            operation="build_plan_rubric_basis",
            source="quality_runtime",
            success=False,
            user_id=getattr(plan, "student_id", None),
            plan_id=getattr(plan, "id", None),
            detail={"reason": "client_unavailable"},
        )
        return {"enabled": False, "project_node_id": None, "basis": {}, "warnings": []}

    project_node_id = resolve_project_node_id(plan, client=client)
    if not project_node_id:
        track_graph_call(
            graph_type="hypergraph",
            operation="build_plan_rubric_basis",
            source="quality_runtime",
            success=False,
            user_id=getattr(plan, "student_id", None),
            plan_id=getattr(plan, "id", None),
            detail={"reason": "project_node_not_matched"},
        )
        return {"enabled": True, "project_node_id": None, "basis": {}, "warnings": ["未匹配到知识图谱项目节点"]}

    context = client.get_project_context(project_node_id)
    nodes = context.get("related_nodes") or []

    buckets: Dict[str, List[Dict[str, Any]]] = {"Market": [], "Technology": [], "Method": [], "Metric": []}
    for node in nodes:
        label = str(node.get("label") or "")
        if label not in buckets:
            continue
        props = node.get("properties") or {}
        name = str(props.get("name") or node.get("id") or "").strip()
        if name:
            buckets[label].append({"id": str(node.get("id") or ""), "name": name})

    market_ids = [item["id"] for item in buckets["Market"]]
    tech_ids = [item["id"] for item in buckets["Technology"]]
    method_ids = [item["id"] for item in buckets["Method"]]
    metric_ids = [item["id"] for item in buckets["Metric"]]

    basis = {
        "R1_problem_market_fit": {
            "evidence": [item["name"] for item in buckets["Market"]],
            "provenance": _node_sources(client, market_ids, limit=12),
            "comment": "市场定义越具体、痛点越明确，得分越高。",
        },
        "R2_solution_feasibility": {
            "evidence": [item["name"] for item in buckets["Technology"] + buckets["Method"]],
            "provenance": _node_sources(client, tech_ids + method_ids, limit=12),
            "comment": "技术路径与方法论同时具备时，落地可行性更强。",
        },
        "R3_measurement": {
            "evidence": [item["name"] for item in buckets["Metric"]],
            "provenance": _node_sources(client, metric_ids, limit=12),
            "comment": "缺少指标通常意味着验证闭环不足。",
        },
    }

    result = {
        "enabled": True,
        "project_node_id": project_node_id,
        "basis": basis,
        "warnings": client.check_consistency(project_node_id),
    }
    track_graph_call(
        graph_type="hypergraph",
        operation="build_plan_rubric_basis",
        source="quality_runtime",
        success=True,
        user_id=getattr(plan, "student_id", None),
        plan_id=getattr(plan, "id", None),
        detail={
            "project_node_id": project_node_id,
            "basis_keys": list((result.get("basis") or {}).keys()),
            "warning_count": len(result.get("warnings") or []),
        },
    )
    return result


