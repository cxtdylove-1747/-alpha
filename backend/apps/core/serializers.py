from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    CaseLibraryDocument,
    CommonIssueReport,
    ConversationRecord,
    MentorshipApplication,
    MessageNotification,
    Plan,
    ProjectRubricScore,
    PromptSceneConfig,
    Rule,
    ReviewRecord,
    RubricItem,
    ScoringRubric,
    TeacherIntervention,
    TeacherChatRecord,
    EvidenceRecord,
)

User = get_user_model()


def _safe_issue_description(item):
    if isinstance(item, dict):
        return str(item.get("description") or item.get("title") or item.get("text") or "").strip()
    return str(item or "").strip()


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    account_no = serializers.SerializerMethodField()

    def get_is_admin(self, obj):
        return bool(
            getattr(obj, "is_staff", False)
            or getattr(obj, "is_superuser", False)
            or getattr(obj, "role", "") == getattr(User, "ROLE_ADMINISTER", "administer")
        )

    def get_name(self, obj):
        full_name = str(getattr(obj, "full_name", "") or "").strip()
        if full_name:
            return full_name
        first = str(getattr(obj, "first_name", "") or "").strip()
        last = str(getattr(obj, "last_name", "") or "").strip()
        if first or last:
            return f"{first}{last}".strip()
        return str(getattr(obj, "username", "") or "").strip()

    def get_account_no(self, obj):
        role = str(getattr(obj, "role", "") or "").strip().lower()
        if role == getattr(User, "ROLE_STUDENT", "student"):
            return str(getattr(obj, "student_no", "") or "").strip() or str(getattr(obj, "username", "") or "").strip()
        if role == getattr(User, "ROLE_TEACHER", "teacher"):
            return str(getattr(obj, "teacher_no", "") or "").strip() or str(getattr(obj, "username", "") or "").strip()
        return str(getattr(obj, "username", "") or "").strip()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "account_no",
            "name",
            "full_name",
            "organization",
            "student_no",
            "teacher_no",
            "email",
            "first_name",
            "last_name",
            "role",
            "major",
            "subject",
            "coaching_direction",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_admin",
            "date_joined",
            "last_login",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    college = serializers.CharField(write_only=True, required=False, allow_blank=True)
    student_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    teacher_id = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "email",
            "role",
            "name",
            "college",
            "student_id",
            "teacher_id",
            "major",
            "subject",
            "coaching_direction",
        ]
        extra_kwargs = {
            "username": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "major": {"required": False, "allow_blank": True},
            "subject": {"required": False, "allow_blank": True},
            "coaching_direction": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        role = str(attrs.get("role") or "").strip().lower() or getattr(User, "ROLE_STUDENT", "student")
        attrs["role"] = role

        raw_username = str(attrs.get("username") or "").strip()
        student_id = str(attrs.get("student_id") or "").strip()
        teacher_id = str(attrs.get("teacher_id") or "").strip()

        account = raw_username
        if role == getattr(User, "ROLE_STUDENT", "student"):
            account = student_id or raw_username
        elif role == getattr(User, "ROLE_TEACHER", "teacher"):
            account = teacher_id or raw_username
        account = str(account or "").strip()

        if not account:
            if role == getattr(User, "ROLE_STUDENT", "student"):
                raise serializers.ValidationError("学生注册必须填写学号")
            raise serializers.ValidationError("教师注册必须填写工号")

        if User.objects.filter(username=account).exists():
            raise serializers.ValidationError("账号已存在，请直接登录")

        if role == getattr(User, "ROLE_STUDENT", "student") and User.objects.filter(student_no=account).exists():
            raise serializers.ValidationError("学号已存在，请直接登录")
        if role == getattr(User, "ROLE_TEACHER", "teacher") and User.objects.filter(teacher_no=account).exists():
            raise serializers.ValidationError("工号已存在，请直接登录")

        attrs["username"] = account
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        name = str(validated_data.pop("name", "") or "").strip()
        college = str(validated_data.pop("college", "") or "").strip()
        student_id = str(validated_data.pop("student_id", "") or "").strip()
        teacher_id = str(validated_data.pop("teacher_id", "") or "").strip()

        role = str(validated_data.get("role") or "").strip().lower()
        username = str(validated_data.get("username") or "").strip()
        student_no = (student_id or username) if role == getattr(User, "ROLE_STUDENT", "student") else None
        teacher_no = (teacher_id or username) if role == getattr(User, "ROLE_TEACHER", "teacher") else None

        user = User(
            **validated_data,
            full_name=name,
            organization=college,
            student_no=student_no,
            teacher_no=teacher_no,
        )
        if not getattr(user, "role", ""):
            user.role = getattr(User, "ROLE_STUDENT", "student")
        if name and not str(getattr(user, "first_name", "") or "").strip():
            user.first_name = name
        user.set_password(password)
        user.save()
        return user

    def validate_role(self, value):
        role = str(value or "").strip().lower() or getattr(User, "ROLE_STUDENT", "student")
        if role not in {getattr(User, "ROLE_STUDENT", "student"), getattr(User, "ROLE_TEACHER", "teacher")}:
            raise serializers.ValidationError("注册仅支持 student 或 teacher 角色")
        return role


class ConversationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationRecord
        fields = ["id", "stage", "question", "answer", "metadata", "created_at"]


class PlanSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.display_name", read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "student",
            "student_name",
            "title",
            "version",
            "pdf_file",
            "file_size",
            "page_count",
            "parsed_pages",
            "extracted_text",
            "status",
            "note",
            "created_at",
        ]
        read_only_fields = ["student", "version", "extracted_text", "status", "file_size", "page_count", "parsed_pages"]


class ReviewRecordSerializer(serializers.ModelSerializer):
    core_issues = serializers.SerializerMethodField()
    optimization_directions = serializers.SerializerMethodField()

    def get_core_issues(self, obj):
        rows = []
        for item in (obj.issues or []):
            text = _safe_issue_description(item)
            if text:
                rows.append(text)
        return rows

    def get_optimization_directions(self, obj):
        return obj.suggestions or []

    class Meta:
        model = ReviewRecord
        fields = [
            "id",
            "plan",
            "reviewer",
            "audience_role",
            "issues",
            "annotations",
            "guidance_questions",
            "examples",
            "suggestions",
            "review_meta",
            "summary",
            "core_issues",
            "optimization_directions",
            "created_at",
        ]


class CaseLibraryDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseLibraryDocument
        fields = [
            "id",
            "title",
            "source_path",
            "source_format",
            "normalized_pdf_path",
            "page_count",
            "industry_category",
            "score_tags",
            "core_facts",
            "is_synthetic",
            "clean_status",
            "privacy_masked",
            "updated_at",
        ]


class PromptSceneConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptSceneConfig
        fields = [
            "id",
            "scene_key",
            "scene_name",
            "fixed_prompt",
            "scene_prompts",
            "output_schema",
            "is_active",
            "updated_at",
        ]


class ScoringRubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringRubric
        fields = [
            "id",
            "code",
            "label",
            "weight",
            "scoring_standard",
            "prompt_hint",
            "is_active",
            "updated_at",
        ]


class MentorshipApplicationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.display_name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.display_name", read_only=True)

    class Meta:
        model = MentorshipApplication
        fields = [
            "id",
            "student",
            "student_name",
            "teacher",
            "teacher_name",
            "startup_direction",
            "demand_note",
            "status",
            "reject_reason",
            "audit_action",
            "audited_at",
            "audited_by",
            "created_at",
        ]
        read_only_fields = ["student", "status", "reject_reason", "audit_action", "audited_at", "audited_by"]


class MessageNotificationSerializer(serializers.ModelSerializer):
    created_at_text = serializers.SerializerMethodField()

    def get_created_at_text(self, obj):
        if not obj.created_at:
            return ""
        dt = timezone.localtime(obj.created_at, timezone.get_fixed_timezone(480))
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    class Meta:
        model = MessageNotification
        fields = ["id", "title", "content", "is_read", "created_at", "created_at_text"]


class CommonIssueReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommonIssueReport
        fields = ["id", "problem_type", "frequency", "sample_case", "created_at"]


class TeacherChatRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherChatRecord
        fields = ["id", "context_type", "question", "answer", "created_at"]


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = [
            "id",
            "rule_id",
            "rule_type",
            "description",
            "condition",
            "severity",
            "trigger_message",
            "impact",
            "fix_task",
            "is_active",
            "updated_at",
        ]


class RubricItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricItem
        fields = [
            "id",
            "rubric_id",
            "name",
            "description",
            "weight",
            "required_evidence",
            "is_active",
            "updated_at",
        ]


class ProjectRubricScoreSerializer(serializers.ModelSerializer):
    rubric_item = RubricItemSerializer(read_only=True)
    rubric_id = serializers.CharField(source="rubric_item.rubric_id", read_only=True)
    rubric_name = serializers.CharField(source="rubric_item.name", read_only=True)

    class Meta:
        model = ProjectRubricScore
        fields = [
            "id",
            "project",
            "rubric_item",
            "rubric_id",
            "rubric_name",
            "score",
            "evidence_quotes",
            "computed_by",
            "created_at",
            "updated_at",
        ]


class EvidenceRecordSerializer(serializers.ModelSerializer):
    rule_id = serializers.CharField(source="rule.rule_id", read_only=True)
    rubric_id = serializers.CharField(source="rubric_item.rubric_id", read_only=True)

    class Meta:
        model = EvidenceRecord
        fields = [
            "id",
            "project",
            "rule",
            "rule_id",
            "rubric_item",
            "rubric_id",
            "source",
            "page",
            "quote",
            "extra",
            "created_at",
        ]


class TeacherInterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherIntervention
        fields = [
            "id",
            "teacher",
            "project",
            "forced_question_points",
            "override_rules",
            "note",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["teacher"]



