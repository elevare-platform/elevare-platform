#!/bin//bash

set -euo pipefail

TIMESTAMP=$(date + %Y%m%d_%H%M%S)
FILENAME="elevare_backup_${TIMESTAMP}.sql.gz"

# Dump and compress
docker exec elevare-db pg_dump -U elevare elevare_db \
  | gzip > /tmp/${FILENAME}

# Upload to R2 backup bucket
aws s3 cp /tmp/${FILENAME} \
  s3://elevare-backups/${FILENAME} \
  --endpoint-url https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com

# Cleanup local file
rm /tmp/${FILENAME}

echo "Backup completed: ${FILENAME}"