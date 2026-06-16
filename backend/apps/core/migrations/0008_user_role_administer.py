from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_rule_rubric_quality_schema"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("student", "Student"), ("teacher", "Teacher"), ("administer", "Administer")],
                default="student",
                max_length=16,
            ),
        ),
    ]

