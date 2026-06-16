from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_user_role_administer"),
    ]

    operations = [
        migrations.CreateModel(
            name="GraphInvocationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "graph_type",
                    models.CharField(
                        choices=[("hypergraph", "Hypergraph"), ("knowledge_graph", "Knowledge Graph")],
                        max_length=24,
                    ),
                ),
                ("operation", models.CharField(max_length=64)),
                ("source", models.CharField(default="runtime", max_length=64)),
                ("success", models.BooleanField(default=True)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="graph_invocations",
                        to="core.plan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="graph_invocations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]

