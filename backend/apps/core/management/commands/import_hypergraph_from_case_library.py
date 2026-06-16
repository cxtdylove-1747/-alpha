from __future__ import annotations

from django.core.management.base import BaseCommand

from ....hypergraph.neo4j_client import get_neo4j_client
from ...models import CaseLibraryDocument


class Command(BaseCommand):
    help = "Import cleaned case library records into Neo4j hypergraph nodes and risk hyperedges."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="Maximum case rows to import")

    def handle(self, *args, **options):
        limit = int(options.get("limit") or 200)
        client = get_neo4j_client()
        if not client.enabled:
            self.stdout.write(self.style.WARNING("Neo4j is disabled; skip import."))
            return

        rows = CaseLibraryDocument.objects.filter(clean_status=CaseLibraryDocument.CLEAN_DONE)[: max(1, limit)]
        imported = 0
        hyperedges = 0

        for row in rows:
            payload = {
                "id": f"case_{row.id}",
                "title": row.title,
                "summary": (row.extracted_text or "")[:1000],
                "outcome": "Unknown",
                "concepts": ["PMF", "TAM", "ValueProposition"],
                "mistakes": [
                    {
                        "type": "evidence_gap",
                        "description": "样本证据链可能不足，需对照 Rubric 补强。",
                    }
                ],
            }
            result = client.import_case(payload)
            if result.get("imported"):
                imported += 1

            edge = {
                "id": f"he_case_{row.id}",
                "type": "RiskPattern",
                "fit_score": 0.5,
                "innovation_index": 0.5,
                "risk_type": "evidence_gap",
                "teaching_note": "结合失败案例路径补充证据链。",
                "members": [
                    {"label": "Case", "id": f"case_{row.id}"},
                ],
            }
            edge_result = client.create_hyperedge(edge)
            if edge_result.get("created"):
                hyperedges += 1

        self.stdout.write(self.style.SUCCESS(f"Imported cases: {imported}, hyperedges: {hyperedges}"))

