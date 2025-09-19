.PHONY: install run test docker-build docker-run clean

# Install dependencies
install:
	pip install -r requirements.txt

# Run locally
run:
	uvicorn app:app --reload --port 8085

# Run tests
test:
	python test-orchestrator.py

# Docker commands
docker-build:
	docker build -t refund-orchestrator .

docker-run:
	docker run -p 8085:8085 --env-file env.example refund-orchestrator

# Clean up
clean:
	docker rmi refund-orchestrator 2>/dev/null || true

# Quick test with curl
test-stripe:
	curl -s http://localhost:8085/refund/stripe \
		-H 'content-type: application/json' \
		-d '{"amount_minor": 1500, "currency":"USD", "psp_ref":"pi_test_123"}' | jq

test-adyen:
	curl -s http://localhost:8085/refund/adyen \
		-H 'content-type: application/json' \
		-d '{"amount_minor": 1500, "currency":"USD", "psp_ref":"test_psp_ref"}' | jq

test-braintree:
	curl -s http://localhost:8085/refund/braintree \
		-H 'content-type: application/json' \
		-d '{"amount_minor": 1500, "currency":"USD", "psp_ref":"test_txn_123"}' | jq

test-shopify:
	curl -s http://localhost:8085/refund/shopify \
		-H 'content-type: application/json' \
		-d '{"amount_minor": 1500, "currency":"USD", "psp_ref":"1234567890"}' | jq

# Health check
health:
	curl -s http://localhost:8085/healthz | jq
