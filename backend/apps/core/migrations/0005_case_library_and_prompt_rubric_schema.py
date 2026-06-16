from django.db import migrations, models


def _table_exists(schema_editor, table_name):
    return table_name in schema_editor.connection.introspection.table_names()


def _column_exists(schema_editor, model, column_name):
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, model._meta.db_table)
    return any(col.name == column_name for col in columns)


def _ensure_schema(apps, schema_editor):
    CaseLibraryDocument = apps.get_model("core", "CaseLibraryDocument")
    PromptSceneConfig = apps.get_model("core", "PromptSceneConfig")
    ScoringRubric = apps.get_model("core", "ScoringRubric")
    ReviewRecord = apps.get_model("core", "ReviewRecord")

    for model in [CaseLibraryDocument, PromptSceneConfig, ScoringRubric]:
        if not _table_exists(schema_editor, model._meta.db_table):
            schema_editor.create_model(model)

    review_meta_field = ReviewRecord._meta.get_field("review_meta")
    if not _column_exists(schema_editor, ReviewRecord, review_meta_field.column):
        schema_editor.add_field(ReviewRecord, review_meta_field)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_case_library_and_prompt_rubric"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="reviewrecord",
                    name="review_meta",
                    field=models.JSONField(blank=True, default=dict),
                ),
                migrations.CreateModel(
                    name="CaseLibraryDocument",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("title", models.CharField(max_length=255)),
                        ("source_path", models.CharField(max_length=1024, unique=True)),
                        (
                            "source_format",
                            models.CharField(
                                choices=[("pdf", "PDF"), ("docx", "DOCX"), ("pptx", "PPTX")],
                                default="pdf",
                                max_length=16,
                            ),
                        ),
                        ("normalized_pdf_path", models.CharField(blank=True, max_length=1024)),
                        ("extracted_text", models.TextField(blank=True)),
                        ("page_count", models.PositiveIntegerField(default=0)),
                        ("industry_category", models.CharField(default="其他", max_length=120)),
                        ("score_tags", models.JSONField(blank=True, default=list)),
                        ("core_facts", models.JSONField(blank=True, default=dict)),
                        ("is_synthetic", models.BooleanField(default=False)),
                        ("source_case_id", models.PositiveIntegerField(blank=True, null=True)),
                        (
                            "clean_status",
                            models.CharField(
                                choices=[("pending", "Pending"), ("done", "Done")],
                                default="pending",
                                max_length=16,
                            ),
                        ),
                        ("privacy_masked", models.BooleanField(default=True)),
                        ("fingerprint", models.CharField(blank=True, max_length=64)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={"ordering": ["-updated_at", "-id"]},
                ),
                migrations.CreateModel(
                    name="PromptSceneConfig",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("scene_key", models.CharField(max_length=64, unique=True)),
                        ("scene_name", models.CharField(max_length=120)),
                        ("fixed_prompt", models.TextField()),
                        ("scene_prompts", models.JSONField(blank=True, default=dict)),
                        ("output_schema", models.JSONField(blank=True, default=dict)),
                        ("is_active", models.BooleanField(default=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={"ordering": ["scene_key"]},
                ),
                migrations.CreateModel(
                    name="ScoringRubric",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("code", models.CharField(max_length=32, unique=True)),
                        ("label", models.CharField(max_length=120)),
                        ("weight", models.PositiveIntegerField(default=20)),
                        ("scoring_standard", models.TextField()),
                        ("prompt_hint", models.TextField(blank=True)),
                        ("is_active", models.BooleanField(default=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={"ordering": ["code"]},
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(_ensure_schema, migrations.RunPython.noop),
    ]



