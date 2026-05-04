"""Merge migration: collapse the two leaf nodes that emerged when the
Layered Recovery Mesh foundation (Unit 1) and the Shamir generalization
(Unit 3) landed in parallel.

Both 0008_wrapped_dek and 0010_recoveryshard_secret_type chained off
0007_recoveryshard_status, leaving Django's migration DAG with two
leaf nodes. ``manage.py migrate`` refuses to apply that, hence the
CI failure:

    CommandError: Conflicting migrations detected; multiple leaf
    nodes in the migration graph: (0008_wrapped_dek,
    0010_recoveryshard_secret_type in auth_module).

This migration is a no-op merge (no new operations) — it exists only
to give the DAG a single leaf node so subsequent migrations can chain
linearly off it.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0008_wrapped_dek'),
        ('auth_module', '0010_recoveryshard_secret_type'),
    ]

    operations = []
