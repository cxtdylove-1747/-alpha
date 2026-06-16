from __future__ import annotations

import io
import random
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.core.models import MentorshipRelation, Plan
from apps.core.services.llm_gateway import call_llm
from docx import Document

User = get_user_model()


def _build_plan_text(project_name: str, include_research: bool) -> str:
    prompt = (
        "请生成一份简洁的创新创业计划书文本，包含：项目名称、痛点、解决方案、商业模式、团队介绍、路演稿。"
        f"项目名称：{project_name}。"
        f"是否包含用户调研：{'是' if include_research else '否'}。"
        "如果包含调研，请出现‘访谈’与‘问卷’字样。"
        "请同时包含TAM/SAM/SOM、LTV、CAC。"
    )
    llm = call_llm(prompt=prompt, system_prompt="你是创新创业教学助理", temperature=0.5, timeout_seconds=30)
    if llm:
        return llm

    base = [
        f"项目名称：{project_name}",
        "痛点描述：中小团队在关键资源、用户验证与商业闭环方面存在明显短板。",
        "解决方案：提供一体化项目诊断、证据链补齐与竞赛辅导服务。",
        "商业模式：订阅+增值服务；TAM 120亿，SAM 18亿，SOM 2.2亿；LTV 1200，CAC 280。",
        "团队介绍：创始人（产品）、技术负责人（AI）、市场负责人（增长）。",
        "路演稿：我们从真实问题出发，用可验证证据推动方案迭代，形成商业闭环。",
    ]
    if include_research:
        base.append("用户调研：已完成访谈 12 次，问卷 180 份，验证核心需求和付费意愿。")
    return "\n".join(base)


def _create_docx_bytes(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        if line.strip():
            doc.add_paragraph(line.strip())
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


class Command(BaseCommand):
    help = "Create 3 demo students, 3 Word plans and submit them to a demo teacher."

    def handle(self, *args, **options):
        teacher, _ = User.objects.get_or_create(
            username="teacher_demo",
            defaults={
                "role": User.ROLE_TEACHER,
                "subject": "创新创业",
                "coaching_direction": "项目诊断与竞赛辅导",
            },
        )
        if not teacher.check_password("Teacher@123"):
            teacher.set_password("Teacher@123")
            teacher.save(update_fields=["password"])

        students = []
        for i in range(1, 4):
            stu, _ = User.objects.get_or_create(
                username=f"student{i}",
                defaults={"role": User.ROLE_STUDENT, "major": "创新创业"},
            )
            if not stu.check_password("Student@123"):
                stu.set_password("Student@123")
                stu.save(update_fields=["password"])
            students.append(stu)
            MentorshipRelation.objects.get_or_create(student=stu, teacher=teacher)

        project_names = ["智链校园", "慧农协同", "医数风控"]
        for idx, stu in enumerate(students):
            name = project_names[idx]
            include_research = idx != 1
            text = _build_plan_text(name, include_research=include_research)
            docx_bytes = _create_docx_bytes(text)

            plan = Plan.objects.create(
                student=stu,
                title=name,
                version=1,
                file_size=len(docx_bytes),
                page_count=1,
                extracted_text=text,
                status=Plan.STATUS_SUBMITTED,
                note="auto-seeded demo project",
            )
            filename = f"{name}_{random.randint(1000, 9999)}.docx"
            plan.pdf_file.save(filename, ContentFile(docx_bytes), save=True)
            self.stdout.write(self.style.SUCCESS(f"created submitted plan: {stu.username} -> {name}"))

        self.stdout.write(self.style.SUCCESS("seed_class_demo_projects completed"))

