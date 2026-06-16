from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo student/teacher accounts."

    def handle(self, *args, **options):
        demo_users = [
            {
                "username": "20260001",
                "password": "Student@123",
                "role": "student",
                "student_no": "20260001",
                "full_name": "\u5f20\u6668\u9633",
                "organization": "\u77e5\u884c\u4e66\u9662",
                "major": "\u521b\u4e1a\u7ba1\u7406",
            },
            {
                "username": "T20260001",
                "password": "Teacher@123",
                "role": "teacher",
                "teacher_no": "T20260001",
                "full_name": "\u674e\u660e\u8f69",
                "organization": "\u77e5\u884c\u4e66\u9662",
                "subject": "\u521b\u65b0\u521b\u4e1a",
                "coaching_direction": "\u5546\u4e1a\u8ba1\u5212\u4e66\u4e0e\u8d5b\u4e8b\u6307\u5bfc",
            },
            {
                "username": "student_demo",
                "password": "Student@123",
                "role": "student",
                "student_no": "20260002",
                "full_name": "\u9648\u661f\u6cb3",
                "organization": "\u77e5\u884c\u4e66\u9662",
                "major": "\u521b\u4e1a\u7ba1\u7406",
            },
            {
                "username": "teacher_demo",
                "password": "Teacher@123",
                "role": "teacher",
                "teacher_no": "T20260002",
                "full_name": "\u738b\u6d77\u5b81",
                "organization": "\u77e5\u884c\u4e66\u9662",
                "subject": "\u521b\u65b0\u521b\u4e1a",
                "coaching_direction": "\u5e02\u573a\u4e0e\u8d22\u52a1\u7b56\u7565",
            },
        ]

        for payload in demo_users:
            username = str(payload.get("username") or "").strip()
            student_no = str(payload.get("student_no") or "").strip() or None
            teacher_no = str(payload.get("teacher_no") or "").strip() or None

            user = User.objects.filter(username=username).first()
            if not user and student_no:
                user = User.objects.filter(student_no=student_no).first()
            if not user and teacher_no:
                user = User.objects.filter(teacher_no=teacher_no).first()

            created = False
            if not user:
                user = User(username=username)
                created = True

            if str(user.username or "").strip() != username:
                username_conflict = User.objects.filter(username=username).exclude(id=user.id).exists()
                if not username_conflict:
                    user.username = username

            user.role = payload["role"]
            user.full_name = payload.get("full_name", "")
            user.organization = payload.get("organization", "")
            user.student_no = student_no
            user.teacher_no = teacher_no
            user.major = payload.get("major", "")
            user.subject = payload.get("subject", "")
            user.coaching_direction = payload.get("coaching_direction", "")
            user.is_active = True
            user.set_password(payload["password"])
            user.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f"created: {user.username}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"updated: {user.username}"))
