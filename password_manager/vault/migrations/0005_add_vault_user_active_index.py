"""
Add composite partial index for the most common vault query pattern:
  SELECT ... FROM vault_encryptedvaultitem
  WHERE user_id = ? AND deleted = false
  ORDER BY updated_at DESC

This covers dashboard, vault listing, and search operations.
"""

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0004_encryptedvaultitem_cached_breach_check_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='encryptedvaultitem',
            index=models.Index(
                fields=['user', '-updated_at'],
                name='idx_vault_user_active',
                condition=models.Q(deleted=False),
            ),
        ),
    ]
