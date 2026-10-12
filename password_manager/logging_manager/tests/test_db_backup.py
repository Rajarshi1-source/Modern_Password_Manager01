"""
Backups must survive the pod, be unreadable without an off-cluster key, and
report freshness only on success. Section 9 of
docs/pqc-hybrid-architecture-review.md.
"""

import gzip
import io
import json
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from logging_manager import age_stream
from logging_manager.management.commands import db_backup, restore_drill
from logging_manager.metrics import LAST_SUCCESS, BackupStatusCollector
from logging_manager.models import BackupStatus

IDENTITY, RECIPIENT = age_stream.generate_identity()


def decrypt_file(path, identity=IDENTITY):
    with open(path, 'rb') as f:
        return b''.join(age_stream.decrypt_stream(f, identity))


class AgeStreamTests(SimpleTestCase):
    def _encrypt(self, data, recipient=RECIPIENT, pieces=7000):
        out = io.BytesIO()
        with age_stream.AgeEncryptor(out, recipient) as enc:
            for i in range(0, len(data), pieces):
                enc.write(data[i:i + pieces])
        return out.getvalue()

    def test_round_trip_across_chunk_boundaries(self):
        for size in (0, 1, age_stream.CHUNK - 1, age_stream.CHUNK, age_stream.CHUNK + 1,
                     2 * age_stream.CHUNK, 3 * age_stream.CHUNK + 17):
            data = os.urandom(size)
            ct = self._encrypt(data)
            self.assertTrue(ct.startswith(b'age-encryption.org/v1\n-> X25519 '))
            self.assertEqual(b''.join(age_stream.decrypt_stream(io.BytesIO(ct), IDENTITY)), data, size)

    def test_other_identity_cannot_decrypt(self):
        other, _ = age_stream.generate_identity()
        ct = self._encrypt(b'secret')
        with self.assertRaisesRegex(age_stream.AgeError, 'no stanza'):
            b''.join(age_stream.decrypt_stream(io.BytesIO(ct), other))

    def test_truncation_is_detected(self):
        ct = self._encrypt(os.urandom(3 * age_stream.CHUNK))
        for cut in (len(ct) - 1, len(ct) - age_stream.CHUNK - 16):
            with self.assertRaises(age_stream.AgeError):
                b''.join(age_stream.decrypt_stream(io.BytesIO(ct[:cut]), IDENTITY))

    def test_unclosed_encryptor_output_is_rejected(self):
        out = io.BytesIO()
        enc = age_stream.AgeEncryptor(out, RECIPIENT)
        enc.write(os.urandom(3 * age_stream.CHUNK))
        with self.assertRaises(age_stream.AgeError):
            b''.join(age_stream.decrypt_stream(io.BytesIO(out.getvalue()), IDENTITY))

    def test_header_tampering_is_detected(self):
        ct = bytearray(self._encrypt(b'secret'))
        ct[len(b'age-encryption.org/v1\n-> X25519 ') + 2] ^= 1
        with self.assertRaises(age_stream.AgeError):
            b''.join(age_stream.decrypt_stream(io.BytesIO(bytes(ct)), IDENTITY))

    def test_bad_recipient_rejected(self):
        with self.assertRaises(age_stream.AgeError):
            age_stream.parse_recipient(RECIPIENT[:-1] + ('q' if RECIPIENT[-1] != 'q' else 'p'))


class DbBackupTests(TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        get_user_model().objects.create_user('backup-canary', 'canary@example.com', 'x' * 16)

    def run_backup(self, **kwargs):
        out = io.StringIO()
        call_command('db_backup', output=str(self.dir), recipient=RECIPIENT, stdout=out, **kwargs)
        return out.getvalue()

    def backups(self):
        return sorted(self.dir.glob('backup-*' + db_backup.SUFFIX))

    def test_writes_an_encrypted_jsonl_dump_and_stamps_success(self):
        self.run_backup()
        (path,) = self.backups()
        raw = path.read_bytes()
        self.assertNotIn(b'backup-canary', raw)
        lines = gzip.decompress(decrypt_file(path)).decode().splitlines()
        records = [json.loads(line) for line in lines]
        self.assertIn('backup-canary', {r['fields'].get('username') for r in records})
        self.assertFalse(list(self.dir.glob('*.partial')))

        status = BackupStatus.objects.get(name='db-backup')
        self.assertEqual(status.last_file, path.name)
        self.assertEqual(status.last_size_bytes, len(raw))

    def test_refuses_to_run_without_a_recipient(self):
        with self.assertRaisesRegex(CommandError, 'recipient'):
            call_command('db_backup', output=str(self.dir), recipient='', stdout=io.StringIO())
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_failure_leaves_no_file_and_does_not_stamp(self):
        earlier = timezone.now() - timedelta(days=3)
        BackupStatus.objects.create(name='db-backup', last_success_at=earlier)

        real = call_command

        def failing(name, *args, **kwargs):
            if name == 'dumpdata':
                kwargs['stdout'].write('{"partial": ')
                raise RuntimeError('database went away')
            return real(name, *args, **kwargs)

        with patch.object(db_backup, 'call_command', failing):
            with self.assertRaises(RuntimeError):
                self.run_backup()
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertEqual(BackupStatus.objects.get(name='db-backup').last_success_at, earlier)

    def test_prunes_to_keep(self):
        for ts in ('20200101T000000Z', '20200102T000000Z', '20200103T000000Z'):
            (self.dir / f'backup-{ts}{db_backup.SUFFIX}').write_bytes(b'old')
        (self.dir / f'backup-20200104T000000Z{db_backup.SUFFIX}.partial').write_bytes(b'dead')
        self.run_backup(keep=2)
        names = [p.name for p in self.backups()]
        self.assertEqual(len(names), 2)
        self.assertEqual(names[0], f'backup-20200103T000000Z{db_backup.SUFFIX}')
        self.assertFalse(list(self.dir.glob('*.partial')))


class BackupMetricTests(TestCase):
    def _samples(self):
        return {
            (s.name, s.labels.get('backup')): s.value
            for family in BackupStatusCollector().collect()
            for s in family.samples
        }

    def test_zero_when_no_backup_has_succeeded(self):
        self.assertEqual(self._samples()[(LAST_SUCCESS, 'db-backup')], 0)

    def test_reports_last_success_time(self):
        at = timezone.now() - timedelta(hours=5)
        BackupStatus.objects.create(name='db-backup', last_success_at=at, last_size_bytes=123)
        self.assertAlmostEqual(self._samples()[(LAST_SUCCESS, 'db-backup')], at.timestamp(), places=3)

    def test_database_error_yields_no_sample(self):
        with patch.object(BackupStatus.objects, 'values_list', side_effect=RuntimeError('db down')):
            self.assertEqual(list(BackupStatusCollector().collect()), [])


class RestoreDrillTests(TransactionTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.identity = self.dir / 'identity'
        self.identity.write_text(f'# test key\n{IDENTITY}\n')

    def test_refuses_a_database_that_has_tables(self):
        (self.dir / f'backup-20200101T000000Z{db_backup.SUFFIX}').write_bytes(b'x')
        with self.assertRaisesRegex(CommandError, 'already has'):
            call_command('restore_drill', input=str(self.dir), identity_file=str(self.identity),
                         stdout=io.StringIO())

    def test_restores_the_newest_backup(self):
        User = get_user_model()
        User.objects.create_user('restored-user', 'r@example.com', 'x' * 16)
        call_command('db_backup', output=str(self.dir), recipient=RECIPIENT, stdout=io.StringIO())
        User.objects.all().delete()

        # The test database already has tables; pretend it is the empty drill DB.
        with patch.object(restore_drill.Command, '_existing_tables', return_value=[]):
            out = io.StringIO()
            call_command('restore_drill', input=str(self.dir), identity_file=str(self.identity),
                         stdout=out)
        self.assertIn('Restore drill passed', out.getvalue())
        self.assertTrue(User.objects.filter(username='restored-user').exists())

    def test_wrong_key_fails(self):
        call_command('db_backup', output=str(self.dir), recipient=age_stream.generate_identity()[1],
                     stdout=io.StringIO())
        with patch.object(restore_drill.Command, '_existing_tables', return_value=[]):
            with self.assertRaisesRegex(CommandError, 'could not be read'):
                call_command('restore_drill', input=str(self.dir), identity_file=str(self.identity),
                             stdout=io.StringIO())
