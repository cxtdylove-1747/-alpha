from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_STUDENT = "student"
    ROLE_TEACHER = "teacher"
    ROLE_ADMINISTER = "administer"
    ROLE_CHOICES = (
        (ROLE_STUDENT, "Student"),
        (ROLE_TEACHER, "Teacher"),
        (ROLE_ADMINISTER, "Administer"),
    )

    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    full_name = models.CharField(max_length=64, blank=True)
    organization = models.CharField(max_length=120, blank=True)
    student_no = models.CharField(max_length=32, unique=True, null=True, blank=True)
    teacher_no = models.CharField(max_length=32, unique=True, null=True, blank=True)
    major = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=120, blank=True)
    coaching_direction = models.CharField(max_length=255, blank=True)

    @property
    def display_name(self) -> str:
        if str(self.full_name or "").strip():
            return str(self.full_name).strip()
        first = str(self.first_name or "").strip()
        last = str(self.last_name or "").strip()
        if first or last:
            return f"{first}{last}".strip()
        return str(self.username or "").strip()


class ConversationRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversation_records")
    stage = models.CharField(max_length=64, default="idea")
    question = models.TextField()
    answer = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Plan(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = ((STATUS_DRAFT, "Draft"), (STATUS_SUBMITTED, "Submitted"))

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plans")
    title = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    pdf_file = models.FileField(upload_to="plans/")
    file_size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    parsed_pages = models.JSONField(default=list, blank=True)
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReviewRecord(models.Model):
    ROLE_STUDENT = "student"
    ROLE_TEACHER = "teacher"
    ROLE_CHOICES = ((ROLE_STUDENT, "Student"), (ROLE_TEACHER, "Teacher"))

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    audience_role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    issues = models.JSONField(default=list, blank=True)
    annotations = models.JSONField(default=list, blank=True)
    guidance_questions = models.JSONField(default=list, blank=True)
    examples = models.JSONField(default=list, blank=True)
    suggestions = models.JSONField(default=list, blank=True)
    review_meta = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class MentorshipApplication(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mentor_applications")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_applications")
    startup_direction = models.CharField(max_length=255)
    demand_note = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reject_reason = models.CharField(max_length=255, blank=True)
    audit_action = models.CharField(max_length=16, blank=True)
    audited_at = models.DateTimeField(null=True, blank=True)
    audited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audited_apps")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("student", "teacher")


class MentorshipRelation(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teacher_relations")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_relations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "teacher")


class MessageNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CommonIssueReport(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="issue_reports")
    problem_type = models.CharField(max_length=120)
    frequency = models.PositiveIntegerField(default=0)
    sample_case = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-frequency", "-created_at"]


class TeacherChatRecord(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teacher_chat_records")
    context_type = models.CharField(max_length=32, default="prep")
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CaseLibraryDocument(models.Model):
    FORMAT_PDF = "pdf"
    FORMAT_DOCX = "docx"
    FORMAT_PPTX = "pptx"
    FORMAT_CHOICES = ((FORMAT_PDF, "PDF"), (FORMAT_DOCX, "DOCX"), (FORMAT_PPTX, "PPTX"))

    CLEAN_PENDING = "pending"
    CLEAN_DONE = "done"
    CLEAN_CHOICES = ((CLEAN_PENDING, "Pending"), (CLEAN_DONE, "Done"))

    title = models.CharField(max_length=255)
    source_path = models.CharField(max_length=1024, unique=True)
    source_format = models.CharField(max_length=16, choices=FORMAT_CHOICES, default=FORMAT_PDF)
    normalized_pdf_path = models.CharField(max_length=1024, blank=True)
    extracted_text = models.TextField(blank=True)
    page_count = models.PositiveIntegerField(default=0)
    industry_category = models.CharField(max_length=120, default="其他")
    score_tags = models.JSONField(default=list, blank=True)
    core_facts = models.JSONField(default=dict, blank=True)
    is_synthetic = models.BooleanField(default=False)
    source_case_id = models.PositiveIntegerField(null=True, blank=True)
    clean_status = models.CharField(max_length=16, choices=CLEAN_CHOICES, default=CLEAN_PENDING)
    privacy_masked = models.BooleanField(default=True)
    fingerprint = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class PromptSceneConfig(models.Model):
    scene_key = models.CharField(max_length=64, unique=True)
    scene_name = models.CharField(max_length=120)
    fixed_prompt = models.TextField()
    scene_prompts = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scene_key"]


class ScoringRubric(models.Model):
    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=120)
    weight = models.PositiveIntegerField(default=20)
    scoring_standard = models.TextField()
    prompt_hint = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]


class Rule(models.Model):
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CHOICES = (
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
    )

    rule_id = models.CharField(max_length=10, unique=True)
    rule_type = models.CharField(max_length=64)
    description = models.TextField()
    condition = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    trigger_message = models.TextField()
    impact = models.TextField(blank=True)
    fix_task = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rule_id"]


class RubricItem(models.Model):
    rubric_id = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    weight = models.FloatField()
    required_evidence = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rubric_id"]


class ProjectRubricScore(models.Model):
    project = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="rubric_scores")
    rubric_item = models.ForeignKey(RubricItem, on_delete=models.CASCADE, related_name="project_scores")
    score = models.FloatField(default=0)
    evidence_quotes = models.JSONField(default=list, blank=True)
    computed_by = models.CharField(max_length=64, default="system")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "rubric_item")
        ordering = ["rubric_item__rubric_id"]


class EvidenceRecord(models.Model):
    SOURCE_PDF = "pdf"
    SOURCE_CHAT = "chat"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = (
        (SOURCE_PDF, "PDF"),
        (SOURCE_CHAT, "Chat"),
        (SOURCE_MANUAL, "Manual"),
    )

    project = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="evidence_records")
    rule = models.ForeignKey(Rule, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidences")
    rubric_item = models.ForeignKey(
        RubricItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evidences",
    )
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_PDF)
    page = models.PositiveIntegerField(null=True, blank=True)
    quote = models.TextField()
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TeacherIntervention(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interventions")
    project = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="interventions")
    forced_question_points = models.JSONField(default=list, blank=True)
    override_rules = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class GraphInvocationLog(models.Model):
    GRAPH_HYPERGRAPH = "hypergraph"
    GRAPH_KNOWLEDGE = "knowledge_graph"
    GRAPH_CHOICES = (
        (GRAPH_HYPERGRAPH, "Hypergraph"),
        (GRAPH_KNOWLEDGE, "Knowledge Graph"),
    )

    graph_type = models.CharField(max_length=24, choices=GRAPH_CHOICES)
    operation = models.CharField(max_length=64)
    source = models.CharField(max_length=64, default="runtime")
    success = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="graph_invocations")
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name="graph_invocations")
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

