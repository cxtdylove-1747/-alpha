from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import EvidenceRecord, MentorshipRelation, MessageNotification, Plan, ProjectRubricScore, TeacherIntervention, User
from .services.project_quality import evaluate_project_quality


class QualityPipelineTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="stu1", password="Password123", role=User.ROLE_STUDENT)
        self.teacher = User.objects.create_user(username="tea1", password="Password123", role=User.ROLE_TEACHER)
        self.other_teacher = User.objects.create_user(username="tea2", password="Password123", role=User.ROLE_TEACHER)
        MentorshipRelation.objects.create(student=self.student, teacher=self.teacher)
        plan = Plan.objects.create(
            student=self.student,
            title="测试项目",
            version=1,
            status=Plan.STATUS_SUBMITTED,
            file_size=10,
            page_count=1,
            extracted_text=(
                "我们的目标用户是学生，核心痛点是获取高质量竞赛辅导成本高。"
                "已完成访谈和问卷，包含TAM/SAM/SOM、LTV、CAC与里程碑。"
            ),
        )
        plan.pdf_file.save("demo.pdf", ContentFile(b"%PDF-1.4 demo"), save=True)
        self.plan = plan

    def test_evaluate_project_quality_outputs_rules_and_rubric(self):
        result = evaluate_project_quality(self.plan)
        self.assertIn("triggered_rules", result)
        self.assertIn("rubric", result)
        self.assertIn("total_score_100", result)

    def test_evaluate_project_quality_is_idempotent(self):
        evaluate_project_quality(self.plan)
        scores_1 = ProjectRubricScore.objects.filter(project=self.plan).count()
        evidences_1 = EvidenceRecord.objects.filter(project=self.plan, source=EvidenceRecord.SOURCE_MANUAL).count()

        evaluate_project_quality(self.plan)
        scores_2 = ProjectRubricScore.objects.filter(project=self.plan).count()
        evidences_2 = EvidenceRecord.objects.filter(project=self.plan, source=EvidenceRecord.SOURCE_MANUAL).count()

        self.assertEqual(scores_1, scores_2)
        self.assertEqual(evidences_1, evidences_2)

    def test_project_rubric_score_api(self):
        client = APIClient()
        client.force_authenticate(user=self.student)
        resp = client.get(f"/api/project/{self.plan.id}/rubric-score")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("items", resp.data.get("data", {}))
        self.assertIn("ability_profile", resp.data.get("data", {}))
        self.assertIn("top_risk_rule", resp.data.get("data", {}))

    def test_project_bottleneck_and_evidence_chain_api(self):
        client = APIClient()
        client.force_authenticate(user=self.student)

        bottleneck = client.get(f"/api/project/{self.plan.id}/bottleneck")
        self.assertEqual(bottleneck.status_code, 200)
        self.assertIn("diagnosis", bottleneck.data.get("data", {}))

        chain = client.get(f"/api/project/{self.plan.id}/evidence-chain")
        self.assertEqual(chain.status_code, 200)
        self.assertTrue(isinstance(chain.data.get("data"), list))

    def test_teacher_intervention_permissions(self):
        allowed = APIClient()
        allowed.force_authenticate(user=self.teacher)
        resp = allowed.post(
            "/api/teacher/intervention",
            {"plan_id": self.plan.id, "forced_question_points": ["请证明支付意愿"]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(TeacherIntervention.objects.filter(project=self.plan, teacher=self.teacher, is_active=True).count(), 1)

        denied = APIClient()
        denied.force_authenticate(user=self.other_teacher)
        denied_resp = denied.post(
            "/api/teacher/intervention",
            {"plan_id": self.plan.id, "forced_question_points": ["无权限测试"]},
            format="json",
        )
        self.assertEqual(denied_resp.status_code, 403)

    def test_teacher_aggregate_and_rule_drilldown(self):
        client = APIClient()
        client.force_authenticate(user=self.teacher)

        agg = client.get("/api/teacher/aggregate-dashboard")
        self.assertEqual(agg.status_code, 200)
        self.assertIn("summary", agg.data.get("data", {}))
        self.assertIn("rule_heatmap", agg.data.get("data", {}))

        drill = client.get("/api/teacher/rule-drilldown", {"rule_id": "H5"})
        self.assertEqual(drill.status_code, 200)
        self.assertIn("projects", drill.data.get("data", {}))

        detail = client.get(f"/api/teacher/project/{self.plan.id}/evidence-detail")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("rules", detail.data.get("data", {}))

    def test_hypergraph_import_case_fallback_when_disabled(self):
        client = APIClient()
        client.force_authenticate(user=self.teacher)
        resp = client.post(
            "/api/hypergraph/import-case",
            {
                "id": "case_demo_1",
                "title": "测试案例",
                "summary": "用于验证无Neo4j时的降级返回",
                "concepts": ["PMF"],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("neo4j_enabled", resp.data.get("data", {}))

    def test_paged_endpoints_for_student_home_and_teacher_analytics(self):
        # Prepare extra notifications for pagination and keyword filtering.
        for idx in range(1, 13):
            MessageNotification.objects.create(
                user=self.student,
                title=f"系统消息 {idx}",
                content=f"这是第 {idx} 条通知",
                is_read=(idx % 2 == 0),
            )

        student = APIClient()
        student.force_authenticate(user=self.student)

        plans_resp = student.get("/api/plans", {"page": 1, "page_size": 5, "q": "测试"})
        self.assertEqual(plans_resp.status_code, 200)
        self.assertIn("items", plans_resp.data.get("data", {}))
        self.assertIn("total", plans_resp.data.get("data", {}))

        messages_resp = student.get("/api/messages", {"page": 1, "page_size": 5, "q": "系统消息", "status": "unread"})
        self.assertEqual(messages_resp.status_code, 200)
        self.assertIn("items", messages_resp.data.get("data", {}))
        self.assertIn("total", messages_resp.data.get("data", {}))

        history_resp = student.get("/api/history", {"mode": "stream", "page": 1, "page_size": 5})
        self.assertEqual(history_resp.status_code, 200)
        self.assertIn("items", history_resp.data.get("data", {}))
        self.assertIn("total", history_resp.data.get("data", {}))

        teacher = APIClient()
        teacher.force_authenticate(user=self.teacher)
        metrics_resp = teacher.get("/api/teacher/metrics-stream", {"page": 1, "page_size": 8, "status": "aggregate"})
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertIn("items", metrics_resp.data.get("data", {}))
        self.assertIn("total", metrics_resp.data.get("data", {}))

    def test_p2_p3_endpoints(self):
        student = APIClient()
        student.force_authenticate(user=self.student)
        teacher = APIClient()
        teacher.force_authenticate(user=self.teacher)

        potential = student.get(f"/api/project/{self.plan.id}/potential-report")
        self.assertEqual(potential.status_code, 200)
        self.assertIn("potential_level", potential.data.get("data", {}))

        reasoning = student.get(f"/api/project/{self.plan.id}/hypergraph-reasoning")
        self.assertEqual(reasoning.status_code, 200)
        self.assertIn("neo4j_enabled", reasoning.data.get("data", {}))

        class_report = teacher.get("/api/teacher/class-learning-report")
        self.assertEqual(class_report.status_code, 200)
        self.assertIn("ability_matrix", class_report.data.get("data", {}))

        recall = student.post("/api/agent/case-recall", {"query": "创新创业 AI", "top_k": 3}, format="json")
        self.assertEqual(recall.status_code, 200)
        self.assertIn("items", recall.data.get("data", {}))
        self.assertIn("retrieval_mode", recall.data.get("data", {}))

        workflow = student.post(
            "/api/agent/workflow-orchestrate",
            {"competition": "挑战杯", "topic": "PMF", "text": self.plan.extracted_text},
            format="json",
        )
        self.assertEqual(workflow.status_code, 200)
        self.assertIn("workflow", workflow.data.get("data", {}))

    def test_health_endpoint_public(self):
        client = APIClient()
        resp = client.get("/api/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("message"), "ok")
        self.assertIn("retrieval_mode", resp.data.get("data", {}))
        self.assertIn("workflow_mode", resp.data.get("data", {}))



