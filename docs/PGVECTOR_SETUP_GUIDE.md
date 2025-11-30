# pgvector Setup Guide

## Overview

pgvector is an **optional** PostgreSQL extension that provides efficient similarity search using vector embeddings. It's useful for:

- Large-scale semantic search (>10k breaches)
- Real-time similarity matching
- Advanced ML features

## ⚠️ Important Note

**pgvector is OPTIONAL**. The system will work perfectly fine without it using traditional PostgreSQL queries. Only install if you need:
- Semantic search at scale (>10,000 breaches)
- Sub-second similarity queries
- Advanced ML vector operations

## Prerequisites

- PostgreSQL 11+ (14+ recommended)
- PostgreSQL development headers
- C compiler (gcc)
- Python 3.8+

## Installation

### 1. Install PostgreSQL pgvector Extension

#### Linux (Ubuntu/Debian)

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y postgresql-server-dev-14 gcc make

# Clone and install pgvector
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

#### macOS

```bash
# Install via Homebrew
brew install pgvector

# Or build from source
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

#### Windows

```powershell
# Download pre-built binaries from:
# https://github.com/pgvector/pgvector/releases

# Or use WSL2 with Linux instructions
```

### 2. Enable Extension in PostgreSQL

```sql
-- Connect to your database
psql -U pm_user -d password_manager

-- Create extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 3. Install Python Package

```bash
pip install pgvector
```

### 4. Run Django Migration

```bash
cd password_manager
python manage.py migrate ml_dark_web 0002_add_pgvector_support
```

This will:
- Create the vector extension
- Add vector columns to tables
- Create IVFFlat indexes for fast search

## Verification

### Check Extension

```sql
-- In PostgreSQL
\dx vector

-- Should show:
-- Name   | Version | Schema | Description
-- vector | 0.5.0   | public | vector data type and ivfflat access method
```

### Check Columns

```sql
-- Check if vector columns exist
\d ml_breach_data

-- Should show:
-- content_embedding | vector(768) |
```

### Test in Django

```python
from ml_dark_web.pgvector_service import pgvector_service

# Check if enabled
print(f"pgvector enabled: {pgvector_service.enabled}")

# Generate embedding
embedding = pgvector_service.generate_embedding("test breach content")
print(f"Embedding shape: {embedding.shape if embedding is not None else 'None'}")

# Test similarity search
similar = pgvector_service.find_similar_breaches(embedding, limit=5)
print(f"Found {len(similar)} similar breaches")
```

## Usage

### 1. Generate Embeddings for Breaches

```python
from ml_dark_web.pgvector_service import pgvector_service

# Update single breach
pgvector_service.update_breach_embedding(
    breach_id=123,
    text="Breach description or content"
)

# Batch update all breaches
pgvector_service.batch_update_embeddings(batch_size=100)
```

### 2. Similarity Search

```python
# Search for similar breaches
results = pgvector_service.find_similar_breaches(
    query_embedding=embedding_vector,
    limit=10,
    similarity_threshold=0.7
)

for breach_id, similarity in results:
    print(f"Breach {breach_id}: {similarity:.3f} similarity")
```

### 3. Find Similar Credentials

```python
# Find credentials similar to a query
similar_creds = pgvector_service.find_similar_credentials(
    credential_text="user@example.com",
    limit=10
)
```

## Performance Tuning

### Index Configuration

```sql
-- Adjust lists parameter based on data size
-- Rule of thumb: sqrt(num_rows)

-- For 10,000 breaches
CREATE INDEX ml_breach_data_embedding_idx 
ON ml_breach_data 
USING ivfflat (content_embedding vector_cosine_ops) 
WITH (lists = 100);

-- For 100,000 breaches
CREATE INDEX ml_breach_data_embedding_idx 
ON ml_breach_data 
USING ivfflat (content_embedding vector_cosine_ops) 
WITH (lists = 316);

-- For 1,000,000 breaches
CREATE INDEX ml_breach_data_embedding_idx 
ON ml_breach_data 
USING ivfflat (content_embedding vector_cosine_ops) 
WITH (lists = 1000);
```

### Search Configuration

```sql
-- Adjust probes for speed/accuracy tradeoff
SET ivfflat.probes = 10;  -- Default, good balance
SET ivfflat.probes = 1;   -- Faster, less accurate
SET ivfflat.probes = 20;  -- Slower, more accurate
```

## Troubleshooting

### Error: "extension 'vector' does not exist"

```bash
# Ensure pgvector is installed
sudo make install

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Error: "could not open extension control file"

```bash
# Check PostgreSQL version matches installation
pg_config --version

# Reinstall for correct version
make clean
make PG_CONFIG=/usr/pgsql-14/bin/pg_config
sudo make install PG_CONFIG=/usr/pgsql-14/bin/pg_config
```

### Slow Queries

```sql
-- Analyze index usage
EXPLAIN ANALYZE
SELECT id, content_embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM ml_breach_data
ORDER BY content_embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- Rebuild index if needed
REINDEX INDEX ml_breach_data_embedding_idx;
```

## Uninstalling

If you want to remove pgvector:

```bash
# 1. Reverse Django migration
python manage.py migrate ml_dark_web 0001_initial

# 2. Drop extension in PostgreSQL
DROP EXTENSION IF EXISTS vector CASCADE;

# 3. Uninstall Python package
pip uninstall pgvector
```

## Further Reading

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [pgvector Django Integration](https://github.com/pgvector/pgvector-python)
- [PostgreSQL Vector Operations](https://www.postgresql.org/docs/current/functions-array.html)

## Support

If you encounter issues:

1. Check PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql-14-main.log`
2. Verify Python package: `pip show pgvector`
3. Test basic operations: `SELECT vector_dims('[1,2,3]'::vector);`

