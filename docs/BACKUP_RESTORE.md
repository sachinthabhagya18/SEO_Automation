# Local backup and restore

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-restore.ps1
```

The backup helper uses pg_dump custom format and docker compose cp rather than PowerShell binary redirection. The restore verifier dumps the source, restores into a random `seo_restore_verify_*` database on the same local PostgreSQL service, compares migration counts and drops only that disposable database. It never restores over the application database. This checks logical restoration, not disaster recovery of all volumes or uploaded files.

Keep `.env` and n8n encryption key securely backed up separately. Uploads, n8n PostgreSQL/data, and optional WordPress/MariaDB volumes also need coordinated backups. Full-volume recovery and production retention/encryption remain M8. Changing PostgreSQL init variables does not change an initialized volume. Never remove volumes as a routine fix.
