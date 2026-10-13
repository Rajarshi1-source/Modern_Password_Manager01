"""Prove a backup restores: decrypt, migrate an EMPTY database, load, check.

    python manage.py restore_drill --input /backups --identity-file /drill-key/identity

``--input`` is a backup file or a directory (the newest backup in it is
used). The target database must be empty: the command refuses to run if it
already has tables, so a misconfigured drill cannot load over production.
Run it against a throwaway PostgreSQL (k8s/restore-drill-job.yaml). Exits
non-zero on any failure.
"""

import gzip
import io
import sys
import zlib
from contextlib import contextmanager
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from logging_manager.age_stream import AgeError, decrypt_stream
from logging_manager.management.commands.db_backup import SUFFIX


class _ChunkReader(io.RawIOBase):
    """Readable raw stream over an iterator of byte chunks."""

    def __init__(self, chunks):
        self._chunks = iter(chunks)
        self._pending = b""

    def readable(self):
        return True

    def readinto(self, buf):
        while not self._pending:
            try:
                self._pending = next(self._chunks)
            except StopIteration:
                return 0
        n = min(len(buf), len(self._pending))
        buf[:n] = self._pending[:n]
        self._pending = self._pending[n:]
        return n


@contextmanager
def _stdin(stream):
    saved = sys.stdin
    sys.stdin = stream
    try:
        yield
    finally:
        sys.stdin = saved


class Command(BaseCommand):
    help = "Restore a db_backup file into an empty database and verify it"

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True,
                            help="Backup file, or a directory to take the newest backup from")
        parser.add_argument("--identity-file", required=True,
                            help="age identity (AGE-SECRET-KEY-1...) that the backup was encrypted to")
        parser.add_argument("--min-users", type=int, default=1,
                            help="Fail unless at least this many users were restored")

    def handle(self, *args, **options):
        backup = self._pick(Path(options["input"]))
        identity = Path(options["identity_file"]).read_text(encoding="utf-8")

        existing = self._existing_tables()
        if existing:
            raise CommandError(
                f"Refusing to restore into a database that already has {len(existing)} "
                "tables. The drill must target an empty, throwaway database."
            )

        self.stdout.write(f"Restoring {backup.name} ({backup.stat().st_size} bytes)")
        call_command("migrate", interactive=False, verbosity=0)

        with open(backup, "rb") as raw:
            try:
                plain = io.BufferedReader(_ChunkReader(decrypt_stream(raw, identity)))
                text = io.TextIOWrapper(gzip.GzipFile(fileobj=plain, mode="rb"), encoding="utf-8")
                with _stdin(text):
                    call_command("loaddata", "-", format="jsonl", verbosity=1, stdout=self.stdout)
            except (AgeError, OSError, EOFError, zlib.error) as exc:
                raise CommandError(f"Backup {backup.name} could not be read: {exc}") from exc

        users = get_user_model().objects.count()
        if users < options["min_users"]:
            raise CommandError(f"Restore produced {users} users; expected at least {options['min_users']}")
        self.stdout.write(self.style.SUCCESS(f"Restore drill passed: {backup.name}, {users} users"))

    @staticmethod
    def _existing_tables():
        return connection.introspection.table_names()

    @staticmethod
    def _pick(path):
        if path.is_dir():
            candidates = sorted(path.glob(f"backup-*{SUFFIX}"))
            if not candidates:
                raise CommandError(f"No backups (backup-*{SUFFIX}) in {path}")
            return candidates[-1]
        if not path.is_file():
            raise CommandError(f"{path} does not exist")
        return path
