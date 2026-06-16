from django.core.management.base import BaseCommand

from ...services.rule_engine import RuleEngine
from ...services.rubric_engine import RubricEngine


class Command(BaseCommand):
    help = "Seed default hard rules (H1-H15) and rubric items (R1-R9)."

    def handle(self, *args, **options):
        RuleEngine().bootstrap_defaults()
        RubricEngine().bootstrap_defaults()
        self.stdout.write(self.style.SUCCESS("Quality baseline seeded."))


