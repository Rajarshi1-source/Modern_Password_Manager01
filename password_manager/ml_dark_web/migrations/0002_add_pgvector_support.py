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
    try:
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("✓ pgvector extension created")
    except Exception as e:
        logger.warning(f"Could not create pgvector extension: {e}")
        logger.warning("This is optional - system will work without it")


def add_vector_columns(apps, schema_editor):
    """Add vector columns to models"""
    try:
        # Add vector column to MLBreachData
        schema_editor.execute(
            "ALTER TABLE ml_breach_data ADD COLUMN IF NOT EXISTS content_embedding vector(768);"
        )
        
        # Add vector column to UserCredentialMonitoring
        schema_editor.execute(
            "ALTER TABLE ml_user_credential_monitoring ADD COLUMN IF NOT EXISTS credential_embedding vector(768);"
        )
        
        logger.info("✓ Vector columns added")
    except Exception as e:
        logger.warning(f"Could not add vector columns: {e}")


def create_vector_indexes(apps, schema_editor):
    """Create IVFFlat indexes for fast similarity search"""
    try:
        # Create index on breach data embeddings
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS ml_breach_data_embedding_idx "
            "ON ml_breach_data USING ivfflat (content_embedding vector_cosine_ops) "
            "WITH (lists = 100);"
        )
        
        # Create index on credential embeddings
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS ml_credential_embedding_idx "
            "ON ml_user_credential_monitoring USING ivfflat (credential_embedding vector_cosine_ops) "
            "WITH (lists = 50);"
        )
        
        logger.info("✓ Vector indexes created")
    except Exception as e:
        logger.warning(f"Could not create vector indexes: {e}")


def reverse_migration(apps, schema_editor):
    """Reverse the migration"""
    try:
        # Drop indexes
        schema_editor.execute("DROP INDEX IF EXISTS ml_breach_data_embedding_idx;")
        schema_editor.execute("DROP INDEX IF EXISTS ml_credential_embedding_idx;")
        
        # Drop columns
        schema_editor.execute("ALTER TABLE ml_breach_data DROP COLUMN IF EXISTS content_embedding;")
        schema_editor.execute("ALTER TABLE ml_user_credential_monitoring DROP COLUMN IF EXISTS credential_embedding;")
        
        logger.info("✓ pgvector support removed")
    except Exception as e:
        logger.warning(f"Error during reverse migration: {e}")


class Migration(migrations.Migration):

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

