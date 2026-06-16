from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from ..models import EvidenceRecord, Plan, ProjectRubricScore, RubricItem
from .fact_extractor import extract_facts
from .hypergraph_runtime import build_plan_rubric_basis
from .rule_engine import RuleEngine
from .rubric_engine import RubricEngine


def evaluate_project_quality(plan: Plan, extra_facts: Dict[str, Any] | None = None) -> Dict[str, Any]:
    text = (plan.extracted_text or "").strip()
    facts = extract_facts(text, extra_facts)

    rule_engine = RuleEngine()
    rubric_engine = RubricEngine()
    rule_engine.bootstrap_defaults()
    rubric_engine.bootstrap_defaults()

    triggered = [asdict(item) for item in rule_engine.evaluate(facts)]
    rubric_scores = rubric_engine.evaluate(text, facts)

    # Keep rubric score snapshots idempotent for the latest project text.
    for item in rubric_scores:
        rubric = RubricItem.objects.filter(rubric_id=item.rubric_id).first()
        if not rubric:
            continue
        ProjectRubricScore.objects.update_or_create(
            project=plan,
            rubric_item=rubric,
            defaults={
                "score": item.score,
                "evidence_quotes": item.evidence_quotes,
                "computed_by": "rubric_engine_v1",
            },
        )

    # Store traceable rule and rubric evidence snippets for teacher-side drilldown.
    EvidenceRecord.objects.filter(project=plan, source=EvidenceRecord.SOURCE_MANUAL).delete()
    for rule in triggered:
        EvidenceRecord.objects.create(
            project=plan,
            source=EvidenceRecord.SOURCE_MANUAL,
            quote=rule["trigger_message"],
            extra={"kind": "rule", "severity": rule["severity"], "rule_id": rule["rule_id"]},
        )

    for item in rubric_scores:
        for quote in item.evidence_quotes:
            EvidenceRecord.objects.create(
                project=plan,
                source=EvidenceRecord.SOURCE_MANUAL,
                page=int(quote.get("page") or 1),
                quote=str(quote.get("quote") or ""),
                extra={"kind": "rubric", "rubric_id": item.rubric_id, "keyword": quote.get("keyword")},
            )

    hypergraph_basis = build_plan_rubric_basis(plan)
    for rubric_key, row in (hypergraph_basis.get("basis") or {}).items():
        for evidence in (row.get("evidence") or [])[:8]:
            text = str(evidence or "").strip()
            if not text:
                continue
            EvidenceRecord.objects.create(
                project=plan,
                source=EvidenceRecord.SOURCE_MANUAL,
                quote=text,
                extra={"kind": "hypergraph", "rubric_key": rubric_key, "project_node_id": hypergraph_basis.get("project_node_id")},
            )

        for source in (row.get("provenance") or [])[:10]:
            source_text = str(source.get("text") or "").strip()
            source_file = str(source.get("file") or "").strip()
            quote = source_text or source_file
            if not quote:
                continue
            EvidenceRecord.objects.create(
                project=plan,
                source=EvidenceRecord.SOURCE_MANUAL,
                quote=quote,
                extra={
                    "kind": "hypergraph_provenance",
                    "rubric_key": rubric_key,
                    "project_node_id": hypergraph_basis.get("project_node_id"),
                    "node_id": source.get("node_id"),
                    "node_label": source.get("node_label"),
                    "node_name": source.get("node_name"),
                    "file": source_file,
                    "competition": source.get("competition"),
                },
            )

    total = 0.0
    weighted = []
    for item in rubric_scores:
        rubric = RubricItem.objects.filter(rubric_id=item.rubric_id).first()
        if not rubric:
            continue
        weighted_score = item.score * float(rubric.weight)
        total += weighted_score
        weighted.append(
            {
                "rubric_id": item.rubric_id,
                "name": rubric.name,
                "weight": rubric.weight,
                "score": item.score,
                "weighted_score": round(weighted_score, 2),
                "evidence_quotes": item.evidence_quotes,
            }
        )

    return {
        "facts": facts,
        "triggered_rules": triggered,
        "rubric": weighted,
        "hypergraph_rubric_basis": hypergraph_basis,
        "weighted_total": round(total, 2),
        "total_score_100": round(total * 10, 2),
    }


