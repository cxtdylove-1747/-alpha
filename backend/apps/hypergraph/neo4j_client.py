from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from . import cypher_queries as cq

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional dependency in local dev
    GraphDatabase = None


class Neo4jClient:
    def __init__(self) -> None:
        self.uri = os.getenv("NEO4J_URI", "")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self._driver = None

        if self.uri and self.password and GraphDatabase is not None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    @property
    def enabled(self) -> bool:
        return self._driver is not None

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()

    def run(self, query: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        with self._driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    def import_case(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"imported": False, "reason": "neo4j-disabled"}

        case = cq.normalize_case_payload(payload)
        if not case["id"] or not case["title"]:
            return {"imported": False, "reason": "case-id-or-title-missing"}

        with self._driver.session(database=self.database) as session:
            session.run(cq.merge_case_query(), case)
            for concept in case["concepts"]:
                session.run(cq.link_case_to_concept_query(), {"case_id": case["id"], "concept_name": concept})
            for mistake in case["mistakes"]:
                session.run(
                    cq.link_case_to_mistake_query(),
                    {
                        "case_id": case["id"],
                        "mistake_type": str(mistake.get("type") or "unknown"),
                        "mistake_desc": str(mistake.get("description") or ""),
                    },
                )

        return {"imported": True, "case_id": case["id"]}

    def create_hyperedge(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"created": False, "reason": "neo4j-disabled"}

        edge = cq.normalize_hyperedge_payload(payload)
        if not edge["id"]:
            return {"created": False, "reason": "hyperedge-id-missing"}

        with self._driver.session(database=self.database) as session:
            session.run(cq.create_hyperedge_query(), edge)
            for member in edge["members"]:
                label = str(member.get("label") or "")
                member_id = str(member.get("id") or "")
                if not label or not member_id:
                    continue
                session.run(
                    cq.attach_member_query(label),
                    {
                        "hyperedge_id": edge["id"],
                        "member_id": member_id,
                    },
                )
        return {"created": True, "hyperedge_id": edge["id"]}

    def project_risk_hyperedges(self, project_id: str) -> List[Dict[str, Any]]:
        return self.run(cq.query_project_risk_hyperedges(), {"pid": project_id})

    def failure_cases_by_technology(self, technology_name: str) -> List[Dict[str, Any]]:
        return self.run(cq.query_failure_by_technology(), {"tech": technology_name})


def get_neo4j_client() -> Neo4jClient:
    return Neo4jClient()

