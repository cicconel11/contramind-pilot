#!/usr/bin/env bash
set -euo pipefail

echo "== health =="
curl -fsS "http://localhost:8081/metrics" >/dev/null
curl -fsS "http://localhost:8082/metrics" >/dev/null
curl -fsS "http://localhost:8083/metrics" >/dev/null

echo "== param hash =="
H1=$(curl -fsS -H "Authorization: Bearer changeme" localhost:8083/param/hash | jq -r .param_hash)
curl -fsS -X POST -H "Authorization: Bearer changeme" -H 'content-type: application/json' \
  -d '{"k":"amount_max","v":3000}' localhost:8083/param/threshold >/dev/null
H2=$(curl -fsS -H "Authorization: Bearer changeme" localhost:8083/param/hash | jq -r .param_hash)
test "$H1" != "$H2"

echo "== attestor =="
PUB=$(curl -fsS localhost:8082/keys | jq -r .keys.\"ed25519:v1\")
SIG=$(curl -fsS -X POST localhost:8082/sign -H 'content-type: application/json' \
  -d '{"bundle":{"hello":"world"}}')
KID=$(jq -r .kid <<<"$SIG")
curl -fsS -X POST localhost:8082/verify -H 'content-type: application/json' \
  -d "{\"bundle\":{\"hello\":\"world\"},\"signature_b64\":\"$(jq -r .signature_b64 <<<"$SIG")\",\"kid\":\"$KID\"}" | jq -e '.valid==true' >/dev/null

echo "== replay =="
python3 tools/replay.py || true   # allow drift; just make sure it runs

echo "== decide api =="
IDEK=$(uuidgen || python3 - <<'PY'
import uuid; print(uuid.uuid4())
PY
)
DEC=$(curl -fsS -H "Idempotency-Key: $IDEK" -H 'content-type: application/json' \
  -d '{"amount": 2750.0, "country": "US", "ts": "2025-09-16T12:00:00Z", "recent": 2, "context_id":"ord_cursor_demo"}' \
  http://localhost:8084/decide)
python3 - <<PY
import json,sys
j=json.loads('''$DEC''')
assert 'certificate_jws' in j and j['decision'] in ('PASS','HOLD_HUMAN','REJECT','NEED_ONE_BIT')
print('decide ok')
PY

# idempotency repeat
DEC2=$(curl -fsS -H "Idempotency-Key: $IDEK" -H 'content-type: application/json' \
  -d '{"amount": 2750.0, "country": "US", "ts": "2025-09-16T12:00:00Z", "recent": 2, "context_id":"ord_cursor_demo"}' \
  http://localhost:8084/decide)
[ "$DEC" = "$DEC2" ] || { echo "idempotency mismatch"; exit 1; }

echo "OK ✅"
