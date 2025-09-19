.PHONY: up down logs test rotate anchor replay ps decide cert-verify

up:
	docker compose up --build -d

down:
	docker compose down -v

ps:
	docker compose ps

logs:
	docker compose logs -f --since=1m

test:
	docker run --rm -it --network=contramind-pilot_default \
	  -e PGHOST=cm-postgres -e PGPORT=5432 -e PGPASSWORD=cm \
	  -v "$$PWD/tests":/tests python:3.11-slim \
	  bash -lc "pip install -q pytest hypothesis psycopg[binary]==3.2.1 && pytest -q /tests"

rotate:
	docker compose exec -e ATTESTOR_ACTIVE_KID=v2 attestor sh -lc 'kill 1'

anchor:
	docker compose up -d anchor

replay:
	python3 tools/replay.py

smoke:
	./smoke-test.sh

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

decide:
	curl -s -H 'content-type: application/json' \
	 -d '{"amount": 1500.0, "country":"US", "ts":"2025-09-16T12:00:00Z", "recent":1}' \
	 http://localhost:8084/decide | jq .

cert-verify:
	JWS=$$(curl -s -H 'content-type: application/json' \
	 -d '{"amount": 1500.0, "country":"US", "ts":"2025-09-16T12:00:00Z", "recent":1}' \
	 http://localhost:8084/decide | jq -r .certificate_jws); \
	python3 tools/verify_cert.py $$JWS
