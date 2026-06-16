from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_extended_requirements"),
    ]

    operations = [
        migrations.CreateModel(
            name="Rule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_id", models.CharField(max_length=10, unique=True)),
                ("rule_type", models.CharField(max_length=64)),
                ("description", models.TextField()),
                ("condition", models.TextField()),
                (
                    "severity",
                    models.CharField(
                        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                        default="medium",
                        max_length=10,
                    ),
                ),
                ("trigger_message", models.TextField()),
                ("impact", models.TextField(blank=True)),
                ("fix_task", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["rule_id"]},
        ),
        migrations.CreateModel(
            name="RubricItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rubric_id", models.CharField(max_length=10, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField()),
                ("weight", models.FloatField()),
                ("required_evidence", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["rubric_id"]},
        ),
        migrations.CreateModel(
            name="ProjectRubricScore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("score", models.FloatField(default=0)),
                ("evidence_quotes", models.JSONField(blank=True, default=list)),
                ("computed_by", models.CharField(default="system", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rubric_scores", to="core.plan"),
                ),
                (
                    "rubric_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_scores",
                        to="core.rubricitem",
                    ),
                ),
            ],
            options={"ordering": ["rubric_item__rubric_id"], "unique_together": {("project", "rubric_item")}},
        ),
        migrations.CreateModel(
            name="EvidenceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[("pdf", "PDF"), ("chat", "Chat"), ("manual", "Manual")],
                        default="pdf",
                        max_length=16,
                    ),
                ),
                ("page", models.PositiveIntegerField(blank=True, null=True)),
                ("quote", models.TextField()),
                ("extra", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_records", to="core.plan"),
                ),
                (
                    "rubric_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evidences",
                        to="core.rubricitem",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evidences",
                        to="core.rule",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TeacherIntervention",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("forced_question_points", models.JSONField(blank=True, default=list)),
                ("override_rules", models.JSONField(blank=True, default=list)),
                ("note", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interventions", to="core.plan"),
                ),
                (
                    "teacher",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interventions", to="core.user"),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
    ]

