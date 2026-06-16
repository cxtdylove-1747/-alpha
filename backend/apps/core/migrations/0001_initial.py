from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(error_messages={"unique": "A user with that username already exists."}, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.", max_length=150, unique=True, verbose_name="username")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email address")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(auto_now_add=True, verbose_name="date joined")),
                ("role", models.CharField(choices=[("student", "Student"), ("teacher", "Teacher")], default="student", max_length=16)),
                ("major", models.CharField(blank=True, max_length=120)),
                ("subject", models.CharField(blank=True, max_length=120)),
                ("coaching_direction", models.CharField(blank=True, max_length=255)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="CommonIssueReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("problem_type", models.CharField(max_length=120)),
                ("frequency", models.PositiveIntegerField(default=0)),
                ("sample_case", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="issue_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-frequency", "-created_at"]},
        ),
        migrations.CreateModel(
            name="ConversationRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage", models.CharField(default="idea", max_length=64)),
                ("question", models.TextField()),
                ("answer", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversation_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MentorshipApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("startup_direction", models.CharField(max_length=255)),
                ("demand_note", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("reject_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentor_applications", to=settings.AUTH_USER_MODEL)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_applications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("student", "teacher")}},
        ),
        migrations.CreateModel(
            name="MentorshipRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_relations", to=settings.AUTH_USER_MODEL)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_relations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("student", "teacher")}},
        ),
        migrations.CreateModel(
            name="MessageNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("content", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("version", models.PositiveIntegerField(default=1)),
                ("pdf_file", models.FileField(upload_to="plans/")),
                ("extracted_text", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted")], default="draft", max_length=24)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReviewRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("audience_role", models.CharField(choices=[("student", "Student"), ("teacher", "Teacher")], max_length=16)),
                ("issues", models.JSONField(blank=True, default=list)),
                ("guidance_questions", models.JSONField(blank=True, default=list)),
                ("suggestions", models.JSONField(blank=True, default=list)),
                ("summary", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="core.plan")),
                ("reviewer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]

