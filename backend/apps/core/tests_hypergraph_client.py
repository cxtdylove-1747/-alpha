from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from ..hypergraph.hypergraph_client import HypergraphClient
from .services.hypergraph_runtime import build_plan_diagnosis, build_plan_rubric_basis


class HypergraphClientTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)

        self.nodes_path = root / "kg_nodes.json"
        self.relations_path = root / "kg_relations.json"
        self.hyperedges_path = root / "hypergraph_edges.json"

        nodes = {
            "nodes": [
                {"id": "Project_1", "label": "Project", "properties": {"name": "智造闭环项目"}},
                {"id": "Project_2", "label": "Project", "properties": {"name": "绿色能源项目"}},
                {"id": "Market_1", "label": "Market", "properties": {"name": "智能制造"}},
                {"id": "Market_2", "label": "Market", "properties": {"name": "新能源"}},
                {"id": "Technology_1", "label": "Technology", "properties": {"name": "数字孪生"}},
                {"id": "Method_1", "label": "Method", "properties": {"name": "A/B测试"}},
                {"id": "Metric_1", "label": "Metric", "properties": {"name": "转化率"}},
                {"id": "Mistake_1", "label": "Mistake", "properties": {"name": "市场验证不足"}},
                {"id": "Resource_1", "label": "Resource", "properties": {"name": "挑战杯", "provider": "挑战杯"}},
            ]
        }
        relations = {
            "relations": [
                {"from": "Project_1", "to": "Market_1", "type": "TARGETS_MARKET", "properties": {}},
                {"from": "Project_1", "to": "Technology_1", "type": "HAS_TECHNOLOGY", "properties": {}},
                {"from": "Project_1", "to": "Method_1", "type": "USES_METHOD", "properties": {}},
                {"from": "Project_1", "to": "Metric_1", "type": "HAS_METRIC", "properties": {}},
                {"from": "Project_1", "to": "Mistake_1", "type": "EXEMPLIFIES_MISTAKE", "properties": {}},
                {"from": "Project_1", "to": "Resource_1", "type": "PARTICIPATES_IN", "properties": {}},
                {"from": "Project_2", "to": "Market_1", "type": "TARGETS_MARKET", "properties": {}},
                {"from": "Project_2", "to": "Technology_1", "type": "HAS_TECHNOLOGY", "properties": {}},
                {"from": "Project_2", "to": "Market_2", "type": "TARGETS_MARKET", "properties": {}},
            ]
        }
        hyperedges = {
            "hyperedges": [
                {
                    "id": "HE_1",
                    "type": "ValueLoop",
                    "member_node_ids": ["Project_1", "Market_1", "Technology_1"],
                    "properties": {"evidence": ["完成首轮POC验证"]},
                },
                {
                    "id": "HE_2",
                    "type": "RiskPattern",
                    "member_node_ids": ["Project_1", "Mistake_1"],
                    "properties": {"evidence": ["用户访谈样本不足"]},
                },
            ]
        }

        self.nodes_path.write_text(json.dumps(nodes, ensure_ascii=False), encoding="utf-8")
        self.relations_path.write_text(json.dumps(relations, ensure_ascii=False), encoding="utf-8")
        self.hyperedges_path.write_text(json.dumps(hyperedges, ensure_ascii=False), encoding="utf-8")

        self.client = HypergraphClient(self.nodes_path, self.relations_path, self.hyperedges_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_indexes(self):
        self.assertIn("Project_1", self.client.node_by_id)
        self.assertEqual(len(self.client.nodes_by_label["Project"]), 2)
        self.assertGreaterEqual(len(self.client.relations_from["Project_1"]), 1)
        self.assertGreaterEqual(len(self.client.hyperedges_by_member["Project_1"]), 1)

    def test_find_nodes_by_name(self):
        ids = self.client.find_nodes_by_name("智造闭环")
        self.assertIn("Project_1", ids)

    def test_get_related_hyperedges(self):
        edges = self.client.get_related_hyperedges(["Project_1"], hyperedge_types=["ValueLoop"])
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["id"], "HE_1")

    def test_get_project_context(self):
        context = self.client.get_project_context("Project_1")
        self.assertEqual(context["project_id"], "Project_1")
        self.assertGreater(context["stats"]["relation_count"], 0)
        self.assertEqual(context["stats"]["mistake_count"], 1)

    def test_find_similar_projects(self):
        similar = self.client.find_similar_projects("Project_1", top_k=3)
        self.assertTrue(similar)
        self.assertEqual(similar[0]["project_id"], "Project_2")

    def test_check_consistency(self):
        warnings = self.client.check_consistency("Project_2")
        self.assertTrue(any("ValueLoop" in item for item in warnings))
        self.assertTrue(any("Method" in item for item in warnings))

    def test_extract_entities_with_llm_callback(self):
        def fake_llm(text, _, __):
            self.assertIn("智能制造", text)
            return ["智能制造"]

        client = HypergraphClient(
            self.nodes_path,
            self.relations_path,
            self.hyperedges_path,
            llm_extract_fn=fake_llm,
        )
        ids = client.extract_entities_from_text("我们聚焦智能制造赛道")
        self.assertIn("Market_1", ids)

    def test_diagnose_project(self):
        report = self.client.diagnose_project("Project_1")
        self.assertTrue(report["enabled"])
        self.assertEqual(report["input_type"], "project_id")
        self.assertEqual((report.get("matched_project") or {}).get("id"), "Project_1")
        self.assertIn("consistency_alerts", report)
        self.assertIn("missing_node_labels", report)
        self.assertIn("risk_patterns", report)
        self.assertIn("Project_1", report["matched_entity_ids"])

    def test_get_competition_resources(self):
        payload = self.client.get_competition_resources("挑战杯")
        self.assertEqual(len(payload["resources"]), 1)
        self.assertEqual(len(payload["projects"]), 1)

    def test_get_common_mistakes(self):
        mistakes = self.client.get_common_mistakes(top_k=5)
        self.assertEqual(mistakes[0]["mistake_id"], "Mistake_1")
        self.assertEqual(mistakes[0]["count"], 1)

    def test_runtime_diagnosis_helper(self):
        plan = SimpleNamespace(title="智造闭环项目", extracted_text="我们面向智能制造，技术为数字孪生")
        report = build_plan_diagnosis(plan, client=self.client)
        self.assertTrue(report["enabled"])
        self.assertEqual(report["resolved_project_node_id"], "Project_1")
        self.assertEqual((report.get("matched_project") or {}).get("id"), "Project_1")
        self.assertIn("consistency_alerts", report)
        self.assertIn("missing_node_labels", report)
        self.assertIn("risk_patterns", report)
        self.assertIn("provenance", report)
        self.assertIn("node_sources", report["provenance"])

    def test_runtime_rubric_basis_helper(self):
        plan = SimpleNamespace(title="智造闭环项目", extracted_text="")
        basis = build_plan_rubric_basis(plan, client=self.client)
        self.assertTrue(basis["enabled"])
        self.assertEqual(basis["project_node_id"], "Project_1")
        self.assertIn("R1_problem_market_fit", basis["basis"])
        self.assertIn("provenance", basis["basis"]["R1_problem_market_fit"])

    def test_compact_hypergraph_context_contains_new_fields(self):
        plan = SimpleNamespace(title="智造闭环项目", extracted_text="")
        report = build_plan_diagnosis(plan, client=self.client)
        compact = _compact_hypergraph_context(report)
        self.assertIn("consistency_alerts", compact)
        self.assertIn("missing_node_labels", compact)
        self.assertIn("risk_patterns", compact)
        self.assertIn("matched_project", compact)




