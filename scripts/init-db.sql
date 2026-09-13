-- PostgreSQL initialisation for the docker-compose stack.
--
-- docker-compose.yml has always mounted this file into
-- /docker-entrypoint-initdb.d/init.sql, but it did not exist in the repository.
-- A bind mount of a missing host path makes Docker create a DIRECTORY there, so
-- the entrypoint found a directory where it expected a script -- silently doing
-- nothing useful on every fresh stack.
--
-- Runs only on FIRST initialisation of an empty data directory. It is never
-- re-run against an existing volume, so keep everything here idempotent anyway.

-- Vector similarity search for ml_dark_web.
--
-- ml_dark_web/migrations/0002_add_pgvector_support.py also issues this, but it
-- deliberately swallows failures ("this is optional - system will work without
-- it"), which means a missing extension degrades silently rather than loudly.
-- Creating it up front means the migration finds it already present on a fresh
-- stack, instead of depending on the application role holding CREATE EXTENSION
-- rights at migrate time.
CREATE EXTENSION IF NOT EXISTS vector;

-- Deliberately nothing else. In particular the GIN index built by
-- vault/migrations/0014 is over EncryptedVaultItem.tags, which is a
-- models.JSONField -> jsonb, and GIN on jsonb uses the built-in jsonb_ops
-- operator class. It needs no btree_gin and no pg_trgm.
