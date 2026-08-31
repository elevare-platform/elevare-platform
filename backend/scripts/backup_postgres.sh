#!/bin/bash
set -euo pipefail

# Requires (from backend/.env.production): R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL
# Requires: aws CLI installed on the host, R2_BACKUP_BUCKET pre-created in Cloudflare R2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env.production"

read_env_var() {
  local key="$1"
  [ -f "${ENV_FILE}" ] || return 0
  grep -E "^${key}=" "${ENV_FILE}" | tail -n1 | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

: "${R2_ACCESS_KEY_ID:=$(read_env_var R2_ACCESS_KEY_ID)}"
: "${R2_SECRET_ACCESS_KEY:=$(read_env_var R2_SECRET_ACCESS_KEY)}"
: "${R2_ENDPOINT_URL:=$(read_env_var R2_ENDPOINT_URL)}"
: "${R2_BACKUP_BUCKET:=$(read_env_var R2_BACKUP_BUCKET)}"
: "${R2_BACKUP_BUCKET:=elevare-backups}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="elevare_backup_${TIMESTAMP}.sql.gz"

export AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}"

# Dump and compress
docker exec elevare-db pg_dump -U elevare elevare_db \
  | gzip > "/tmp/${FILENAME}"

# Upload to R2 backup bucket
aws s3 cp "/tmp/${FILENAME}" \
  "s3://${R2_BACKUP_BUCKET}/${FILENAME}" \
  --endpoint-url "${R2_ENDPOINT_URL}"

# Cleanup local file
rm "/tmp/${FILENAME}"

echo "Backup completed: ${FILENAME}"
