from __future__ import annotations

from typing import Any, Dict, Iterable, List

# Canonical labels used by the innovation hypergraph.
NODE_LABELS = {
    "Project": "Project",
    "Technology": "Technology",
    "Market": "Market",
    "Resource": "Resource",
    "Participant": "Participant",
    "Outcome": "Outcome",
    "Concept": "Concept",
    "Method": "Method",
    "Task": "Task",
    "Artifact": "Artifact",
    "Metric": "Metric",
    "Case": "Case",
    "RubricItem": "RubricItem",
    "Mistake": "Mistake",
    "Evidence": "Evidence",
    "Hyperedge": "Hyperedge",
}

RELATIONSHIPS = {
    "USES": "USES",
    "TARGETS": "TARGETS",
    "PRODUCES": "PRODUCES",
    "EVALUATED_BY": "EVALUATED_BY",
    "HAS_EVIDENCE": "HAS_EVIDENCE",
    "APPLIES_TO": "APPLIES_TO",
    "MEASURED_BY": "MEASURED_BY",
    "REQUIRES": "REQUIRES",
    "COMMON_IN": "COMMON_IN",
    "FIXED_BY": "FIXED_BY",
    "EXEMPLIFIES": "EXEMPLIFIES",
    "DEMONSTRATES": "DEMONSTRATES",
    "MEMBER_OF": "MEMBER_OF",
}


def merge_case_query() -> str:
    return """
    MERGE (c:Case {id: $id})
    SET c.title = $title,
        c.summary = $summary,
        c.outcome = $outcome,
        c.updated_at = datetime()
    """


def link_case_to_concept_query() -> str:
    return """
    MATCH (c:Case {id: $case_id})
    MERGE (n:Concept {name: $concept_name})
    MERGE (c)-[:EXEMPLIFIES]->(n)
    """


def link_case_to_mistake_query() -> str:
    return """
    MATCH (c:Case {id: $case_id})
    MERGE (m:Mistake {type: $mistake_type})
    SET m.description = coalesce($mistake_desc, m.description)
    MERGE (c)-[:DEMONSTRATES]->(m)
    """


def create_hyperedge_query() -> str:
    return """
    MERGE (he:Hyperedge {id: $id})
    SET he.type = $type,
        he.fit_score = $fit_score,
        he.innovation_index = $innovation_index,
        he.risk_type = $risk_type,
        he.teaching_note = $teaching_note,
        he.updated_at = datetime()
    """


def attach_member_query(label: str) -> str:
    return f"""
    MATCH (n:{label} {{id: $member_id}})
    MATCH (he:Hyperedge {{id: $hyperedge_id}})
    MERGE (n)-[:MEMBER_OF]->(he)
    """


def query_project_risk_hyperedges() -> str:
    return """
    MATCH (p:Project {id: $pid})-[:MEMBER_OF]->(he:Hyperedge {type: 'RiskPattern'})
    RETURN he, [(he)<-[:MEMBER_OF]-(n) | n] AS members
    """


def query_failure_by_technology() -> str:
    return """
    MATCH (t:Technology {name: $tech})<-[:USES]-(p:Project)-[:MEMBER_OF]->(he:Hyperedge {type: 'RiskPattern'})
    MATCH (he)<-[:MEMBER_OF]-(o:Outcome {status: 'Fail'})
    RETURN o.fail_reason AS fail_reason, count(*) AS freq
    ORDER BY freq DESC
    """


def normalize_case_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(payload.get("id") or ""),
        "title": str(payload.get("title") or ""),
        "summary": str(payload.get("summary") or ""),
        "outcome": str(payload.get("outcome") or "Unknown"),
        "concepts": [str(x) for x in (payload.get("concepts") or []) if str(x).strip()],
        "mistakes": [x for x in (payload.get("mistakes") or []) if isinstance(x, dict)],
    }


def normalize_hyperedge_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(payload.get("id") or ""),
        "type": str(payload.get("type") or "RiskPattern"),
        "fit_score": float(payload.get("fit_score") or 0),
        "innovation_index": float(payload.get("innovation_index") or 0),
        "risk_type": str(payload.get("risk_type") or ""),
        "teaching_note": str(payload.get("teaching_note") or ""),
        "members": [x for x in (payload.get("members") or []) if isinstance(x, dict)],
    }


def unique_member_labels(members: Iterable[Dict[str, Any]]) -> List[str]:
    labels = []
    for member in members:
        label = str(member.get("label") or "")
        if label in NODE_LABELS.values() and label not in labels:
            labels.append(label)
    return labels

