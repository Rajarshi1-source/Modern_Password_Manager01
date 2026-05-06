"""Add a partial unique constraint on
``RecoveryWrappedDEK(user, factor_type)`` WHERE ``status='active'``.

Without this, two concurrent first-time enrolls of the same
``(user, factor_type)`` combination both find zero existing rows under
their per-row ``select_for_update()`` locks (because there are no rows
to lock) and both succeed in inserting ACTIVE rows. The lookup view's
``order_by('-created_at').first()`` then silently returns the most
recent of the duplicates while older ACTIVE rows remain live, stranding
recovery artifacts behind an endpoint that no longer surfaces them.

The existing partial unique on ``recovery_key`` covers only that one
factor_type. This migration extends the invariant to *every* factor
type so the storage layer enforces what the application layer cannot.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0012_time_locked_recovery'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='recoverywrappeddek',
            constraint=models.UniqueConstraint(
                fields=['user', 'factor_type'],
                condition=models.Q(status='active'),
                name='unique_active_factor_per_user_per_type',
            ),
        ),
    ]
