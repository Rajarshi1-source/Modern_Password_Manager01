# Valet key pattern — cloud vault backups

Large encrypted backups should not always stream through the API server. This project supports **scoped, short-lived credentials** (presigned URLs) so the **client uploads or downloads bytes directly** from **Google Cloud Storage** or **Amazon S3**, while the API retains metadata and authorization.

## Configuration

| Setting | Purpose |
|---------|---------|
| `CLOUD_STORAGE_BUCKET` + GCS credentials | Google Cloud Storage |
| `AWS_STORAGE_BUCKET_NAME` + `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 |
| `PRESIGNED_URL_TTL_SECONDS` | URL lifetime (default **900** seconds / 15 minutes) |

Service account / IAM user must be allowed to **sign** URLs (GCS: service account with private key; AWS: access keys with `s3:PutObject` / `s3:GetObject` on the backup prefix).

## API flow (upload)

1. **POST** `/api/vault/backups/start-cloud-upload/` (authenticated)  
   - Creates a `VaultBackup` row with `cloud_sync_status=pending` and metadata placeholder `{"cloud_only": true, "v": 1}`.  
   - Returns `upload_url`, `method: PUT`, `Content-Type` header expectation, `expires_in`, and `cloud_path`.

2. **Client** issues **HTTP PUT** to `upload_url` with the **encrypted backup body** (same format as server-mediated backups: JSON vault export or envelope format).

3. **POST** `/api/vault/backups/{id}/complete-cloud-upload/` with optional `size` (bytes).  
   - Marks `cloud_sync_status=synced`.

## API flow (download)

1. **GET** `/api/vault/backups/{id}/cloud-download-url/`  
   - Returns a short-lived **GET** presigned URL for the object at `cloud_storage_path`.

2. **Client** downloads the blob and decrypts client-side as usual.

## Restore behavior

`restore` detects `cloud_only` metadata, downloads the object from storage, then runs the same decryption path as inline backups ([password_manager/vault/views/backup_views.py](../password_manager/vault/views/backup_views.py)).

## Security notes

- URLs expire quickly; scope is limited to the object path generated server-side (`backups/{user_id}/{backup_id}`).
- **Authorization** remains on the API (JWT); presigned URLs are issued only to the owning user.
- Prefer **TLS** for PUT/GET to the cloud vendor endpoints (default for GCS/S3).

## Implementation reference

- [password_manager/vault/services/cloud_storage.py](../password_manager/vault/services/cloud_storage.py) — `generate_presigned_put_url`, `generate_presigned_get_url`, GCS and S3 backends.
