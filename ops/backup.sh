#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +%F_%H%M%S)
docker exec cm-postgres pg_dump -U cm -d cm -Fp > "ops/backups/cm_${STAMP}.sql"
ls -1t ops/backups/cm_*.sql | tail -n +8 | xargs -r rm -f
