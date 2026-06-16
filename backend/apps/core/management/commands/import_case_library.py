from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...case_ingest import export_case_core_table, ingest_case_library


class Command(BaseCommand):
	help = "Import case files from data/ into structured case library."

	def add_arguments(self, parser):
		parser.add_argument("--data-root", default=str(Path(settings.BASE_DIR).parent / "data"), help="Case root directory")
		parser.add_argument(
			"--normalized-dir",
			default=str(Path(settings.MEDIA_ROOT) / "case_library" / "normalized"),
			help="Directory for normalized PDFs",
		)
		parser.add_argument("--no-synthetic", action="store_true", help="Disable synthetic supplement generation")
		parser.add_argument(
			"--table-output",
			default=str(Path(settings.BASE_DIR) / "media" / "case_library" / "core_info_table.json"),
			help="Output path for extracted core info table",
		)

	def handle(self, *args, **options):
		data_root = options["data_root"]
		normalized_dir = options["normalized_dir"]
		include_synthetic = not options["no_synthetic"]

		result = ingest_case_library(
			data_root=data_root,
			project_root=str(Path(settings.BASE_DIR).parent),
			normalized_dir=normalized_dir,
			include_synthetic=include_synthetic,
		)
		table_file = export_case_core_table(options["table_output"])

		self.stdout.write(self.style.SUCCESS("Case ingestion completed."))
		self.stdout.write(f"scanned={result['scanned']} imported={result['imported']} skipped={result['skipped']}")
		self.stdout.write(f"synthetic_created={result['synthetic_created']}")
		if result["errors"]:
			self.stdout.write(self.style.WARNING(f"errors={len(result['errors'])} (showing first 5)"))
			for line in result["errors"][:5]:
				self.stdout.write(self.style.WARNING(line))
		self.stdout.write(f"core_info_table={table_file}")

