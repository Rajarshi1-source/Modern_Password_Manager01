"""
Add composite partial index for the most common vault query pattern:
  SELECT ... FROM vault_encryptedvaultitem
  WHERE user_id = ? AND deleted = false
  ORDER BY updated_at DESC

This covers dashboard, vault listing, and search operations.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0004_encryptedvaultitem_cached_breach_check_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vault_user_active "
                "ON vault_encryptedvaultitem (user_id, updated_at DESC) "
                "WHERE deleted = false;"
            ),
            reverse_sql="DROP INDEX IF EXISTS idx_vault_user_active;",
        ),
    ]
