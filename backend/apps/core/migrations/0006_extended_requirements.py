from django.db import migrations


class Migration(migrations.Migration):
	"""
	This migration file was previously empty, which causes Django to raise
	BadMigrationError on startup. Keep it as an explicit no-op checkpoint.
	"""

	dependencies = [
		("core", "0005_case_library_and_prompt_rubric_schema"),
	]

	operations = []


