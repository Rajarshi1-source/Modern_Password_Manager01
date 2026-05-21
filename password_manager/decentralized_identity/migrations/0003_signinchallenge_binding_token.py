"""
Audit fix C9 (2026-05): bind each sign-in nonce to a per-session token
echoed via an HttpOnly+Secure cookie, preventing cross-device VP replay.

Existing rows are backfilled with the empty string. The verify path
treats empty `binding_token` as "legacy challenge, no cookie required"
so we don't break already-issued challenges in flight.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            'decentralized_identity',
            '0002_rename_did_challenge_consumed_idx_decentraliz_did_str_2e093f_idx_and_more',
        ),
    ]

    operations = [
        migrations.AddField(
            model_name='signinchallenge',
            name='binding_token',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    "Server-issued token echoed via a per-session cookie. "
                    "Required on verify when present; legacy rows (created "
                    "before C9 fix) have an empty string and are honored "
                    "for backward compat until they expire."
                ),
                max_length=128,
            ),
        ),
    ]
