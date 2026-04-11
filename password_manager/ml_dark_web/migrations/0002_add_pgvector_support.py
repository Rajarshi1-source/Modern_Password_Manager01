"""
Migration to add pgvector support for similarity search

Note: This migration is OPTIONAL and requires:
1. PostgreSQL database
2. pgvector extension installed
3. pgvector Python package

Installation:
    pip install pgvector
    
    # In PostgreSQL:
    CREATE EXTENSION IF NOT EXISTS vector;
"""

from django.db import migrations
import logging

logger = logging.getLogger(__name__)


def create_pgvector_extension(apps, schema_editor):
    """Create pgvector extension in PostgreSQL"""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            logger.info("✓ pgvector extension created")
        except Exception as e:
            logger.warning(f"Could not create pgvector extension: {e}")
            logger.warning("This is optional - system will work without it")
            schema_editor.connection.rollback()


def add_vector_columns(apps, schema_editor):
    """Add vector columns to models"""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute(
                "ALTER TABLE ml_breach_data "
                "ADD COLUMN IF NOT EXISTS content_embedding bytea;"
            )
            cursor.execute(
                "ALTER TABLE ml_user_credential_monitoring "
                "ADD COLUMN IF NOT EXISTS credential_embedding bytea;"
            )
            logger.info("✓ Vector columns added")
        except Exception as e:
            logger.warning(f"Could not add vector columns: {e}")
            schema_editor.connection.rollback()


def create_vector_indexes(apps, schema_editor):
    """
    Create IVFFlat indexes for fast similarity search.
    Only attempted when the vector extension is actually installed.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector';"
            )
            if not cursor.fetchone():
                logger.info(
                    "pgvector extension not installed — skipping vector indexes"
                )
                return
        except Exception:
            schema_editor.connection.rollback()
            return

        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS ml_breach_data_embedding_idx "
                "ON ml_breach_data USING ivfflat (content_embedding vector_cosine_ops) "
                "WITH (lists = 100);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS ml_credential_embedding_idx "
                "ON ml_user_credential_monitoring "
                "USING ivfflat (credential_embedding vector_cosine_ops) "
                "WITH (lists = 50);"
            )
            logger.info("✓ Vector indexes created")
        except Exception as e:
            logger.warning(f"Could not create vector indexes: {e}")
            schema_editor.connection.rollback()


def reverse_migration(apps, schema_editor):
    """Reverse the migration"""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute(
                "DROP INDEX IF EXISTS ml_breach_data_embedding_idx;"
            )
            cursor.execute(
                "DROP INDEX IF EXISTS ml_credential_embedding_idx;"
            )
            cursor.execute(
                "ALTER TABLE ml_breach_data "
                "DROP COLUMN IF EXISTS content_embedding;"
            )
            cursor.execute(
                "ALTER TABLE ml_user_credential_monitoring "
                "DROP COLUMN IF EXISTS credential_embedding;"
            )
            logger.info("✓ pgvector support removed")
        except Exception as e:
            logger.warning(f"Error during reverse migration: {e}")
            schema_editor.connection.rollback()


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('ml_dark_web', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_pgvector_extension,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            add_vector_columns,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            create_vector_indexes,
            reverse_code=reverse_migration
        ),
    ]
