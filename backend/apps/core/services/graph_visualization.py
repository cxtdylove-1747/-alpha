import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from django.conf import settings

GRAPH_FILE_SET_PRIORITY: tuple[tuple[str, str, str, str], ...] = (
    # The admin visualization should show the full graph exported under backend/data
    # by default. Keep the smaller v1v2 export only as an explicit fallback.
    ("full", "kg_nodes.json", "kg_relations.json", "hypergraph_edges.json"),
    ("v1v2", "kg_nodes_v1v2.json", "kg_relations_v1v2.json", "hypergraph_edges_v1v2.json"),
)


def _graph_data_candidates() -> list[Path]:
    roots: list[Path] = []
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

    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    return deduped


def _load_graph_dataset() -> dict[str, Any]:
    errors: list[str] = []
    preferred_dataset = str(os.getenv("GRAPH_DATASET") or "full").strip().lower()
    allow_auto_freshness = preferred_dataset in {"auto", "latest", "freshest"}

    for root in _graph_data_candidates():
        ranked_sets: list[dict[str, Any]] = []
        for priority, (dataset, nodes_name, relations_name, hyperedges_name) in enumerate(GRAPH_FILE_SET_PRIORITY):
            if not allow_auto_freshness and preferred_dataset and dataset.lower() != preferred_dataset:
                # In normal admin usage this locks the source to the large backend/data
                # files. Set GRAPH_DATASET=v1v2 or GRAPH_DATASET=auto to override.
                continue
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
            ranked_sets.append(
                {
                    "dataset": dataset,
                    "priority": priority,
                    "nodes_path": nodes_path,
                    "relations_path": relations_path,
                    "hyperedges_path": hyperedges_path,
                    "freshness": freshness,
                }
            )

        if allow_auto_freshness:
            ranked_sets.sort(key=lambda row: (int(row["freshness"]), -int(row["priority"])), reverse=True)
        else:
            ranked_sets.sort(key=lambda row: int(row["priority"]))
        for row in ranked_sets:
            dataset = str(row["dataset"])
            nodes_path = row["nodes_path"]
            relations_path = row["relations_path"]
            hyperedges_path = row["hyperedges_path"]
            try:
                with nodes_path.open("r", encoding="utf-8") as fp:
                    nodes_payload = json.load(fp) or {}
                with relations_path.open("r", encoding="utf-8") as fp:
                    relations_payload = json.load(fp) or {}
                with hyperedges_path.open("r", encoding="utf-8") as fp:
                    hyperedges_payload = json.load(fp) or {}
                nodes = nodes_payload.get("nodes") or []
                relations = relations_payload.get("relations") or []
                hyperedges = hyperedges_payload.get("hyperedges") or []
                if not isinstance(nodes, list) or not isinstance(relations, list) or not isinstance(hyperedges, list):
                    raise ValueError("graph payload must contain list fields")
                return {
                    "nodes": nodes,
                    "relations": relations,
                    "hyperedges": hyperedges,
                    "dataset": dataset,
                    "source_root": str(root),
                    "source_files": {
                        "nodes": str(nodes_path),
                        "relations": str(relations_path),
                        "hyperedges": str(hyperedges_path),
                    },
                    "source_mtime_ns": int(row["freshness"]),
                    "load_error": "",
                }
            except Exception as exc:
                errors.append(f"{dataset}@{root}: {exc}")

    return {
        "nodes": [],
        "relations": [],
        "hyperedges": [],
        "dataset": "none",
        "source_root": "",
        "source_files": {},
        "source_mtime_ns": 0,
        "load_error": "; ".join(errors[:3]) if errors else "graph files not found",
    }


def _load_kg_payload() -> dict[str, Any]:
    payload = _load_graph_dataset()
    return {
        "nodes": payload.get("nodes") or [],
        "relations": payload.get("relations") or [],
        "dataset": payload.get("dataset") or "none",
        "source_root": payload.get("source_root") or "",
        "source_files": payload.get("source_files") or {},
        "source_mtime_ns": int(payload.get("source_mtime_ns") or 0),
        "load_error": payload.get("load_error") or "",
    }


def _load_hypergraph_payload() -> dict[str, Any]:
    payload = _load_graph_dataset()
    return {
        "hyperedges": payload.get("hyperedges") or [],
        "dataset": payload.get("dataset") or "none",
        "source_root": payload.get("source_root") or "",
        "source_files": payload.get("source_files") or {},
        "source_mtime_ns": int(payload.get("source_mtime_ns") or 0),
        "load_error": payload.get("load_error") or "",
    }


def _safe_int(raw_value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw_value)
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def _build_degree_map(relations: list[dict[str, Any]]) -> dict[str, int]:
    degree: dict[str, int] = {}
    for rel in relations:
        src = str(rel.get("from") or "").strip()
        dst = str(rel.get("to") or "").strip()
        if src:
            degree[src] = degree.get(src, 0) + 1
        if dst:
            degree[dst] = degree.get(dst, 0) + 1
    return degree


def _top_counter(counter: Counter[str], key: str, limit: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, count in counter.most_common(limit):
        label = str(name or "").strip()
        if not label:
            continue
        rows.append({key: label, "count": int(count)})
    return rows


def _rank_kg_nodes(raw_nodes: list[dict[str, Any]], raw_relations: list[dict[str, Any]], limit_nodes: int) -> list[dict[str, Any]]:
    degree = _build_degree_map(raw_relations)

    def score(item: dict[str, Any]) -> Tuple[int, int, str]:
        nid = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        centrality = int(degree.get(nid, 0))
        # Prefer meaningful labels over sparse/unknown nodes.
        label_bonus = 1 if label and label.lower() not in {"entity", "unknown"} else 0
        return (centrality, label_bonus, nid)

    ranked = sorted(raw_nodes, key=score, reverse=True)
    return ranked[:limit_nodes]


def build_knowledge_graph_preview(limit_nodes: int = 220, limit_edges: int = 500) -> dict[str, Any]:
    raw = _load_kg_payload()
    raw_nodes = raw.get("nodes") or []
    raw_relations = raw.get("relations") or []
    total_node_count = len(raw_nodes)
    total_edge_count = len(raw_relations)

    node_limit = _safe_int(limit_nodes, default=180, minimum=30, maximum=400)
    edge_limit = _safe_int(limit_edges, default=360, minimum=80, maximum=1200)

    selected_nodes = _rank_kg_nodes(raw_nodes, raw_relations, node_limit)
    node_ids = {str(item.get("id") or "") for item in selected_nodes if str(item.get("id") or "").strip()}

    categories: list[dict[str, str]] = []
    category_index: dict[str, int] = {}
    nodes = []
    for item in selected_nodes:
        nid = str(item.get("id") or "").strip()
        if not nid:
            continue
        label = str(item.get("label") or "Entity").strip() or "Entity"
        if label not in category_index:
            category_index[label] = len(categories)
            categories.append({"name": label})
        name = str((item.get("properties") or {}).get("name") or nid)
        nodes.append(
            {
                "id": nid,
                "name": name[:60],
                "value": label,
                "category": category_index[label],
                "symbolSize": 14 + min(18, int(math.log2(len(name) + 2) * 3)),
            }
        )

    links = []
    for rel in raw_relations:
        if len(links) >= edge_limit:
            break
        src = str(rel.get("from") or "").strip()
        dst = str(rel.get("to") or "").strip()
        if not src or not dst or src not in node_ids or dst not in node_ids:
            continue
        links.append(
            {
                "source": src,
                "target": dst,
                "value": str(rel.get("type") or "REL"),
                "lineStyle": {"opacity": 0.3},
            }
        )
    node_label_counter = Counter(
        str((item or {}).get("label") or "Entity").strip() or "Entity"
        for item in raw_nodes
        if isinstance(item, dict)
    )
    relation_type_counter = Counter(
        str((rel or {}).get("type") or "REL").strip() or "REL"
        for rel in raw_relations
        if isinstance(rel, dict)
    )

    return {
        "nodes": nodes,
        "links": links,
        "categories": categories,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(links),
            "rendered_node_count": len(nodes),
            "rendered_edge_count": len(links),
            "total_node_count": total_node_count,
            "total_edge_count": total_edge_count,
            "is_truncated": len(nodes) < total_node_count or len(links) < total_edge_count,
            "dataset": raw.get("dataset") or "none",
            "source_root": raw.get("source_root") or "",
            "source_files": raw.get("source_files") or {},
            "source_mtime_ns": int(raw.get("source_mtime_ns") or 0),
            "node_label_count": len(node_label_counter),
            "relation_type_count": len(relation_type_counter),
            "node_label_top": _top_counter(node_label_counter, key="label"),
            "relation_type_top": _top_counter(relation_type_counter, key="type"),
            "load_error": raw.get("load_error") or "",
        },
    }


def _edge_signature(edge_type: str, members: list[str], node_map: dict[str, dict[str, Any]]) -> Tuple[str, str, Tuple[str, ...]]:
    project_anchor = next((x for x in members if str(x).startswith("Project_")), "")
    labels = []
    for mid in members:
        label = str((node_map.get(mid) or {}).get("label") or "Entity")
        labels.append(label)
    labels.sort()
    return edge_type, project_anchor, tuple(labels)


def _edge_quality(edge: dict[str, Any], type_count: dict[str, int], node_map: dict[str, dict[str, Any]]) -> float:
    edge_type = str(edge.get("type") or "Hyperedge").strip() or "Hyperedge"
    members = [str(x).strip() for x in (edge.get("member_node_ids") or []) if str(x).strip()]
    unique_members = list(dict.fromkeys(members))

    score = 0.0
    score += min(4.0, len(unique_members) * 0.7)

    evidence = (edge.get("properties") or {}).get("evidence") or {}
    if isinstance(evidence, dict):
        if str(evidence.get("text") or "").strip():
            score += 2.0
        if str(evidence.get("file") or "").strip():
            score += 1.5
        if str(evidence.get("competition") or "").strip():
            score += 0.8
    elif evidence:
        score += 1.0

    type_freq = int(type_count.get(edge_type, 0))
    score += min(3.0, math.log(type_freq + 1, 2))

    labels = [str((node_map.get(mid) or {}).get("label") or "") for mid in unique_members]
    if any(label == "Project" for label in labels):
        score += 1.2
    if any(label in {"Market", "Technology", "Method", "Metric", "Resource"} for label in labels):
        score += 1.0

    return round(score, 4)


def _rank_hyperedges(all_hyperedges: list[dict[str, Any]], node_map: dict[str, dict[str, Any]], limit_hyperedges: int) -> list[dict[str, Any]]:
    type_count: dict[str, int] = {}
    for edge in all_hyperedges:
        edge_type = str(edge.get("type") or "Hyperedge").strip() or "Hyperedge"
        type_count[edge_type] = type_count.get(edge_type, 0) + 1

    best_by_signature: dict[Tuple[str, str, Tuple[str, ...]], tuple[float, dict[str, Any]]] = {}
    for edge in all_hyperedges:
        members = [str(x).strip() for x in (edge.get("member_node_ids") or []) if str(x).strip()]
        members = list(dict.fromkeys(members))
        if len(members) < 2:
            continue
        edge_type = str(edge.get("type") or "Hyperedge").strip() or "Hyperedge"
        signature = _edge_signature(edge_type, members, node_map)
        quality = _edge_quality(edge, type_count, node_map)

        prev = best_by_signature.get(signature)
        if not prev or quality > prev[0]:
            best_by_signature[signature] = (quality, edge)

    ranked_rows = sorted(best_by_signature.values(), key=lambda item: item[0], reverse=True)
    return [row[1] for row in ranked_rows[:limit_hyperedges]]


def build_hypergraph_preview(limit_hyperedges: int = 120, max_members: int = 6) -> dict[str, Any]:
    raw_kg = _load_kg_payload()
    raw_hypergraph = _load_hypergraph_payload()
    all_hyperedges = raw_hypergraph.get("hyperedges") or []

    hyperedge_limit = _safe_int(limit_hyperedges, default=120, minimum=20, maximum=500)
    member_limit = _safe_int(max_members, default=6, minimum=2, maximum=12)

    node_map = {
        str(item.get("id") or "").strip(): item
        for item in (raw_kg.get("nodes") or [])
        if str(item.get("id") or "").strip()
    }

    ranked_hyperedges = _rank_hyperedges(all_hyperedges, node_map, hyperedge_limit)
    total_hyperedge_count = len(all_hyperedges)
    total_member_node_count = len(node_map)
    hyperedge_type_counter = Counter(
        str((edge or {}).get("type") or "Hyperedge").strip() or "Hyperedge"
        for edge in all_hyperedges
        if isinstance(edge, dict)
    )
    member_label_counter: Counter[str] = Counter()
    for edge in all_hyperedges:
        if not isinstance(edge, dict):
            continue
        members = [str(x).strip() for x in (edge.get("member_node_ids") or []) if str(x).strip()]
        for member_id in dict.fromkeys(members):
            label = str((node_map.get(member_id) or {}).get("label") or "Entity").strip() or "Entity"
            member_label_counter[label] += 1

    categories: list[dict[str, str]] = [{"name": "Hyperedge"}]
    category_index: dict[str, int] = {"Hyperedge": 0}
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    added_ids: set[str] = set()

    def _ensure_member_node(member_id: str):
        if member_id in added_ids:
            return
        raw = node_map.get(member_id) or {}
        label = str(raw.get("label") or "Entity").strip() or "Entity"
        if label not in category_index:
            category_index[label] = len(categories)
            categories.append({"name": label})
        name = str((raw.get("properties") or {}).get("name") or member_id)
        nodes.append(
            {
                "id": member_id,
                "name": name[:60],
                "category": category_index[label],
                "symbolSize": 14,
            }
        )
        added_ids.add(member_id)

    for edge in ranked_hyperedges:
        edge_id = str(edge.get("id") or "").strip()
        if not edge_id:
            continue
        edge_type = str(edge.get("type") or "Hyperedge").strip() or "Hyperedge"
        center_id = f"center::{edge_id}"
        nodes.append(
            {
                "id": center_id,
                "name": f"{edge_type}:{edge_id[-5:]}",
                "category": 0,
                "symbolSize": 18,
                "value": edge_type,
            }
        )
        added_ids.add(center_id)

        members = [str(x).strip() for x in (edge.get("member_node_ids") or []) if str(x).strip()]
        members = list(dict.fromkeys(members))[:member_limit]
        for member_id in members:
            _ensure_member_node(member_id)
            links.append(
                {
                    "source": center_id,
                    "target": member_id,
                    "value": edge_type,
                    "lineStyle": {"opacity": 0.42},
                }
            )

    return {
        "nodes": nodes,
        "links": links,
        "categories": categories,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(links),
            "rendered_node_count": len(nodes),
            "rendered_edge_count": len(links),
            "total_hyperedge_count": total_hyperedge_count,
            "rendered_hyperedge_count": len(ranked_hyperedges),
            "total_member_node_count": total_member_node_count,
            "is_truncated": len(ranked_hyperedges) < total_hyperedge_count,
            "dataset": raw_hypergraph.get("dataset") or "none",
            "source_root": raw_hypergraph.get("source_root") or "",
            "source_files": raw_hypergraph.get("source_files") or {},
            "source_mtime_ns": int(raw_hypergraph.get("source_mtime_ns") or 0),
            "hyperedge_type_count": len(hyperedge_type_counter),
            "hyperedge_type_top": _top_counter(hyperedge_type_counter, key="type"),
            "member_label_count": len(member_label_counter),
            "member_label_top": _top_counter(member_label_counter, key="label"),
            "load_error": raw_hypergraph.get("load_error") or raw_kg.get("load_error") or "",
        },
    }
