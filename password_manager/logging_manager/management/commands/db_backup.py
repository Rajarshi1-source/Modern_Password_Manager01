"""Management command to dump the database to a compressed JSON fixture.

Designed for K8s CronJob scheduling. Writes to stdout by default so the
output can be piped to cloud storage (gsutil cp, aws s3 cp, etc.).

    python manage.py db_backup                       # stdout
    python manage.py db_backup --output /backups/    # writes timestamped file
"""

import gzip
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export full database as gzipped JSON fixture"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Directory to write backup file (omit to write to stdout)",
        )
        parser.add_argument(
            "--exclude",
            nargs="*",
            default=["contenttypes", "auth.Permission", "sessions"],
            help="Models to exclude from the dump",
        )

    def handle(self, *args, **options):
        buf = StringIO()
        call_command(
            "dumpdata",
            "--natural-foreign",
            "--natural-primary",
            "--indent=2",
            *[f"--exclude={e}" for e in (options["exclude"] or [])],
            stdout=buf,
        )
        payload = buf.getvalue().encode("utf-8")

        if options["output"]:
            out_dir = Path(options["output"])
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            filepath = out_dir / f"backup-{ts}.json.gz"
            with gzip.open(filepath, "wb") as f:
                f.write(payload)
            self.stdout.write(self.style.SUCCESS(f"Backup written to {filepath}"))
        else:
            compressed = gzip.compress(payload)
            sys.stdout.buffer.write(compressed)
