from django.db import migrations, models


def _fill_user_profile(apps, schema_editor):
    User = apps.get_model("core", "User")

    for user in User.objects.all().iterator():
        updates = {}
        role = str(getattr(user, "role", "") or "").strip().lower()
        username = str(getattr(user, "username", "") or "").strip()

        if not str(getattr(user, "full_name", "") or "").strip() and username:
            if username == "student_demo":
                updates["full_name"] = "张晨阳"
            elif username == "teacher_demo":
                updates["full_name"] = "李明轩"
            elif username == "admin":
                updates["full_name"] = "平台管理员"
            else:
                updates["full_name"] = username

        if role == "student":
            if not getattr(user, "student_no", None):
                if username == "student_demo":
                    updates["student_no"] = "20260001"
                elif username and username.isdigit():
                    updates["student_no"] = username
            if getattr(user, "teacher_no", None):
                updates["teacher_no"] = None
        elif role == "teacher":
            if not getattr(user, "teacher_no", None):
                if username == "teacher_demo":
                    updates["teacher_no"] = "T20260001"
                elif username and username.upper().startswith("T"):
                    updates["teacher_no"] = username
            if getattr(user, "student_no", None):
                updates["student_no"] = None

        if updates:
            for key, value in updates.items():
                setattr(user, key, value)
            user.save(update_fields=list(updates.keys()))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_graphinvocationlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="full_name",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="organization",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="user",
            name="student_no",
            field=models.CharField(blank=True, max_length=32, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="teacher_no",
            field=models.CharField(blank=True, max_length=32, null=True, unique=True),
        ),
        migrations.RunPython(_fill_user_profile, migrations.RunPython.noop),
    ]
