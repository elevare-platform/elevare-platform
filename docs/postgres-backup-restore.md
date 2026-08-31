# Postgres backup & restore

Backups are produced by `backend/scripts/backup_postgres.sh`, scheduled via cron
on the VPS (daily, 2 AM server time) as the `deploy` user. Each run dumps the
`elevare_db` database from the `elevare-db` container, gzips it, and uploads it
to the `elevare-backups` bucket in Cloudflare R2. Credentials are read from
`backend/.env.production` on the VPS.

## Listing available backups

```bash
aws s3 ls s3://elevare-backups/ --endpoint-url "$R2_ENDPOINT_URL"
```

## Restoring

**Restore into a fresh/empty database first to verify the backup is good**
before touching production data. Restoring directly on top of an existing
database will fail with duplicate-key errors, or silently corrupt state if
forced — don't skip the verification step.

1. Download the backup:
   ```bash
   aws s3 cp s3://elevare-backups/<filename>.sql.gz . \
     --endpoint-url "$R2_ENDPOINT_URL"
   ```

2. Verify it against a scratch database, not production:
   ```bash
   docker exec elevare-db psql -U elevare -c "CREATE DATABASE restore_check;"
   gunzip -c <filename>.sql.gz | docker exec -i elevare-db psql -U elevare -d restore_check
   ```
   Spot-check a few tables (`\dt`, row counts on key tables) inside that database,
   then drop it once satisfied:
   ```bash
   docker exec elevare-db psql -U elevare -c "DROP DATABASE restore_check;"
   ```

3. Only once verified — restoring over the real `elevare_db` (destructive,
   drops existing data first):
   ```bash
   docker exec elevare-db psql -U elevare -c "DROP DATABASE elevare_db;"
   docker exec elevare-db psql -U elevare -c "CREATE DATABASE elevare_db;"
   gunzip -c <filename>.sql.gz | docker exec -i elevare-db psql -U elevare -d elevare_db
   ```

4. Restart the app containers so they reconnect cleanly:
   ```bash
   docker compose -f docker-compose.prod.yml restart api worker worker-ingestion beat
   ```

## Notes

- Redis is not backed up — it holds cache/queue state, not source-of-truth data,
  so it's expected to repopulate on its own after a restart.
- A lifecycle/expiry rule is set on the `elevare-backups` R2 bucket
  (`elevare_backup_delete`, deletes objects after 30 days) so old backups
  don't accumulate indefinitely.
