"""Stream an encrypted database dump to durable storage.

    python manage.py db_backup --output /backups --recipient age1...
    BACKUP_AGE_RECIPIENT=age1... python manage.py db_backup --output /backups

The dump is Django ``dumpdata`` in JSON Lines, gzip-compressed, then encrypted
to an age X25519 PUBLIC key (logging_manager/age_stream.py), so the cluster
that writes backups never holds the key that reads them. Decrypt with
``age -d -i key.txt backup-....jsonl.gz.age | gunzip``; restore with the
``restore_drill`` command or ``loaddata --format=jsonl -``.

Nothing is buffered in memory: dumpdata iterates querysets and each layer
writes through. The file is written as ``*.partial``, fsynced, then renamed,
and only then is BackupStatus stamped (exported as
``vault_backup_last_success_timestamp_seconds``). A failed run leaves no
final file and does not move the timestamp.
"""

import gzip
import io
import os
import sys
import time
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from logging_manager.age_stream import AgeEncryptor, AgeError, parse_recipient

SUFFIX = '.jsonl.gz.age'
JOB_NAME = 'db-backup'
# Twice the CronJob's activeDeadlineSeconds (1800, k8s/cronjobs.yaml).
STALE_PARTIAL_SECONDS = 3600


class Command(BaseCommand):
    help = "Export the database as an age-encrypted, gzipped JSON Lines fixture"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Directory to write the backup into (omit to write to stdout)",
        )
        parser.add_argument(
            "--recipient",
            default=os.environ.get("BACKUP_AGE_RECIPIENT", ""),
            help="age public key (age1...) to encrypt to; default $BACKUP_AGE_RECIPIENT",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=int(os.environ.get("BACKUP_KEEP", "14")),
            help="Number of most recent backups to keep in --output (0 = keep all)",
        )
        parser.add_argument(
            "--exclude",
            nargs="*",
            default=["contenttypes", "auth.Permission", "sessions", "logging_manager.BackupStatus"],
            help="Models to exclude from the dump",
        )

    def handle(self, *args, **options):
        recipient = (options["recipient"] or "").strip()
        if not recipient:
            raise CommandError(
                "No age recipient: pass --recipient or set BACKUP_AGE_RECIPIENT. "
                "Backups are never written unencrypted."
            )
        try:
            parse_recipient(recipient)
        except (AgeError, ValueError) as exc:
            raise CommandError(f"Invalid age recipient: {exc}") from exc

        if not options["output"]:
            # stdout: whoever reads the pipe decides whether it was kept, so
            # this mode never stamps BackupStatus.
            self._dump(sys.stdout.buffer, recipient, options["exclude"])
            sys.stdout.buffer.flush()
            return

        out_dir = Path(options["output"])
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        final = out_dir / f"backup-{ts}{SUFFIX}"
        partial = final.with_name(final.name + ".partial")

        try:
            with open(partial, "wb") as raw:
                self._dump(raw, recipient, options["exclude"])
                raw.flush()
                os.fsync(raw.fileno())
            size = partial.stat().st_size
            os.replace(partial, final)
            _fsync_dir(out_dir)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

        self._stamp(final, size)
        self._prune(out_dir, options["keep"])
        self.stdout.write(self.style.SUCCESS(f"Backup written to {final} ({size} bytes)"))

    @staticmethod
    def _dump(raw, recipient, exclude):
        encryptor = AgeEncryptor(raw, recipient)
        gz = gzip.GzipFile(fileobj=encryptor, mode="wb")
        text = io.TextIOWrapper(gz, encoding="utf-8", newline="\n")
        call_command(
            "dumpdata",
            "--format=jsonl",
            "--natural-foreign",
            "--natural-primary",
            *[f"--exclude={e}" for e in (exclude or [])],
            stdout=text,
        )
        # Close innermost-out: gzip trailer, then the final age chunk. Only
        # reached when dumpdata succeeded; on error the file stays truncated
        # (undecryptable) and is deleted by the caller.
        text.flush()
        text.detach()
        gz.close()
        encryptor.close()

    @staticmethod
    def _stamp(final, size):
        from logging_manager.models import BackupStatus
        BackupStatus.objects.update_or_create(
            name=JOB_NAME,
            defaults={
                "last_success_at": timezone.now(),
                "last_size_bytes": size,
                "last_file": final.name,
            },
        )

    def _prune(self, out_dir, keep):
        if keep <= 0:
            return
        backups = sorted(out_dir.glob(f"backup-*{SUFFIX}"))
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)
            self.stdout.write(f"Pruned {old.name}")
        # Leftovers from runs killed before their own cleanup ran. Only stale
        # ones: a concurrent run (a manual one beside the CronJob) is still
        # writing its own, and its mtime keeps moving while it does.
        cutoff = time.time() - STALE_PARTIAL_SECONDS
        for stale in out_dir.glob(f"backup-*{SUFFIX}.partial"):
            try:
                if stale.stat().st_mtime < cutoff:
                    stale.unlink(missing_ok=True)
            except FileNotFoundError:
                pass


def _fsync_dir(path):
    if os.name != "posix":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
