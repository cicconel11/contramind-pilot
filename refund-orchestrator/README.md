# Refund Orchestrator

A unified FastAPI service that provides provable, idempotent refunds across all major PSPs (Stripe, Adyen, Braintree, Shopify) with built-in JWS certificate verification.

## 🚀 Features

- **Unified API**: Single interface for all PSP refunds
- **JWS Verification**: Offline certificate verification against Attestor keys
- **Idempotency**: Shared idempotency keys across Contramind and PSPs
- **Decision Gating**: Only processes refunds when Contramind decision is `PASS`
- **Metadata Storage**: Stores proof in PSP metadata and your database
- **Production Ready**: Comprehensive error handling and monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your App      │───▶│ Refund           │───▶│ Contramind      │
│                 │    │ Orchestrator     │    │ /decide         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ PSP (Stripe/     │    │ JWS Certificate │
                       │ Adyen/Braintree/ │    │ Verification    │
                       │ Shopify)         │    │                 │
                       └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Run Locally

```bash
# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export $(grep -v '^#' env.example | xargs)  # or create a real .env

# Start the service
uvicorn app:app --reload --port 8085
```

### 2. Docker

```bash
# Build and run
docker build -t refund-orchestrator .
docker run -p 8085:8085 --env-file env.example refund-orchestrator
```

## 📋 API Usage

### Stripe Refund

```bash
curl -s http://localhost:8085/refund/stripe \
  -H 'content-type: application/json' \
  -d '{
    "amount_minor": 2599,
    "currency": "USD", 
    "psp_ref": "pi_test_123",
    "country": "US",
    "recent": 1
  }' | jq
```

### Adyen Refund

```bash
curl -s http://localhost:8085/refund/adyen \
  -H 'content-type: application/json' \
  -d '{
    "amount_minor": 2599,
    "currency": "USD",
    "psp_ref": "YOUR_PSP_REFERENCE",
    "country": "US"
  }' | jq
```

### Braintree Refund

```bash
curl -s http://localhost:8085/refund/braintree \
  -H 'content-type: application/json' \
  -d '{
    "amount_minor": 2599,
    "currency": "USD",
    "psp_ref": "the_original_txn_id",
    "country": "US"
  }' | jq
```

### Shopify Refund

```bash
curl -s http://localhost:8085/refund/shopify \
  -H 'content-type: application/json' \
  -d '{
    "amount_minor": 2599,
    "currency": "USD",
    "psp_ref": "1234567890",
    "country": "US"
  }' | jq
```

## 🔐 Decision Flow

### 1. Refund Request
- Extract PSP reference (charge ID, payment reference, etc.)
- Get customer context (country, recent refunds)
- Generate idempotency key

### 2. Contramind Decision
- Call `/decide` endpoint with refund context
- Receive decision: `PASS`, `HOLD_HUMAN`, `REJECT`, or `NEED_ONE_BIT`
- Get JWS certificate for offline verification

### 3. Certificate Verification
- **Mandatory**: Verify JWS signature against Attestor keys
- **Fail Fast**: If verification fails, never hit PSP
- **Cache Keys**: 5-minute key cache for performance

### 4. PSP Refund Creation
- **PASS**: Create refund with decision metadata
- **HOLD_HUMAN**: Return decision for manual review
- **REJECT**: Return decision without PSP call

### 5. Metadata Storage
- **Database**: Store full JWS certificate locally
- **PSP Metadata**: Store proof ID, key ID, and truncated JWS
- **Audit Trail**: Complete decision history with tamper evidence

## 🏪 PSP-Specific Implementation

### Stripe
- **Metadata**: Decision proof in refund metadata
- **Idempotency**: Shared with Stripe's idempotency system
- **Auto-Detection**: Handles both charge and payment intent IDs

### Adyen
- **Reference**: Custom reference with proof ID
- **Additional Data**: Decision metadata in additionalData
- **Async**: Handles Adyen's async refund flow

### Braintree
- **Custom Fields**: Decision metadata in transaction fields
- **Database Storage**: Full certificate stored in your DB
- **SDK Integration**: Uses official Braintree SDK

### Shopify
- **Metafields**: Decision certificates in order metafields
- **Refund Notes**: Proof ID in refund notes
- **API Integration**: Full Shopify Admin API support

## 🔧 Configuration

### Environment Variables

```bash
# Core Contramind
DECIDER_URL=http://localhost:8084
ATTESTOR_KEYS_URL=http://localhost:8082/keys
VERIFY_TLS=0  # set to 1 in production
DEFAULT_COUNTRY=US

# Stripe
STRIPE_SECRET_KEY=sk_test_...

# Adyen
ADYEN_API_KEY=...
ADYEN_MERCHANT=YourMerchantAccount
ADYEN_BASE_URL=https://checkout-test.adyen.com

# Braintree
BT_ENV=sandbox
BT_MERCHANT_ID=...
BT_PUBLIC_KEY=...
BT_PRIVATE_KEY=...

# Shopify
SHOPIFY_SHOP=your-shop-subdomain
SHOPIFY_TOKEN=shpat_...
SHOPIFY_API_VERSION=2024-07
```

### Docker Compose Integration

```yaml
services:
  refund-orchestrator:
    build: .
    environment:
      DECIDER_URL: "http://decider:8084"
      ATTESTOR_KEYS_URL: "http://attestor:8082/keys"
      VERIFY_TLS: "0"
      DEFAULT_COUNTRY: "US"
      STRIPE_SECRET_KEY: "${STRIPE_SECRET_KEY}"
      ADYEN_API_KEY: "${ADYEN_API_KEY}"
      ADYEN_MERCHANT: "${ADYEN_MERCHANT}"
      ADYEN_BASE_URL: "${ADYEN_BASE_URL}"
      BT_ENV: "sandbox"
      BT_MERCHANT_ID: "${BT_MERCHANT_ID}"
      BT_PUBLIC_KEY: "${BT_PUBLIC_KEY}"
      BT_PRIVATE_KEY: "${BT_PRIVATE_KEY}"
      SHOPIFY_SHOP: "${SHOPIFY_SHOP}"
      SHOPIFY_TOKEN: "${SHOPIFY_TOKEN}"
      SHOPIFY_API_VERSION: "2024-07"
    ports:
      - "8085:8085"
    depends_on:
      - decider
      - attestor
```

## 📊 Response Format

### Success Response

```json
{
  "status": "PASS",
  "decision": "PASS",
  "proof_id": "abc123def456...",
  "kid": "key_2025_01_16",
  "param_hash": "def456ghi789...",
  "psp_response": {
    "refund_id": "re_1234567890"
  }
}
```

### Hold/Reject Response

```json
{
  "status": "HOLD_HUMAN",
  "decision": "HOLD_HUMAN", 
  "proof_id": "abc123def456...",
  "kid": "key_2025_01_16",
  "param_hash": "def456ghi789...",
  "psp_response": null
}
```

## 🔒 Security Features

### JWS Verification
- **Offline Verification**: No Contramind service required
- **Key Caching**: 5-minute cache for performance
- **Signature Validation**: Ed25519 signature verification
- **Payload Validation**: Ensures certificate matches decision

### Idempotency
- **Shared Keys**: Same key used for Contramind and PSP
- **Length Limits**: Automatic truncation for PSP limits
- **Hash Fallback**: SHA256 hash for long contexts

### Error Handling
- **Circuit Breakers**: Prevent cascade failures
- **Fail Fast**: Verify certificates before PSP calls
- **Graceful Degradation**: Return decisions even if PSP fails

## 📈 Monitoring & Observability

### Health Check

```bash
curl http://localhost:8085/healthz
```

Response:
```json
{
  "ok": true,
  "decider": "http://localhost:8084",
  "keys": "http://localhost:8082/keys"
}
```

### Key Metrics
- **Decision Latency**: Time to get Contramind decision
- **Verification Success Rate**: JWS verification success rate
- **PSP Success Rate**: Refund creation success rate
- **Certificate Cache Hit Rate**: Key cache performance

### Logging
- All decision requests and responses
- Certificate verification results
- PSP API calls and responses
- Error conditions and stack traces

## 🚦 Production Deployment

### 1. Environment Setup
- Set `VERIFY_TLS=1` for production
- Use production PSP credentials
- Configure proper logging and monitoring

### 2. Scaling
- Deploy behind load balancer
- Use connection pooling for PSP APIs
- Implement rate limiting

### 3. Monitoring
- Set up health check monitoring
- Monitor decision latency and success rates
- Alert on certificate verification failures

### 4. Security
- Use mTLS for internal communication
- Implement proper key rotation
- Monitor for certificate tampering

## 🆘 Troubleshooting

### Common Issues

**Decision API Unavailable**
```bash
# Check Contramind services
curl http://localhost:8084/healthz
curl http://localhost:8082/keys
```

**Certificate Verification Fails**
```bash
# Check key format
curl http://localhost:8082/keys | jq
```

**PSP Refund Fails**
- Check PSP credentials and permissions
- Verify refund amount and currency
- Check PSP-specific error messages

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn app:app --reload --port 8085
```

## 📚 Additional Resources

- [Decision Certificate Specification](../docs/DECISION_CERTIFICATE_SPEC.md)
- [OpenAPI Specification](../docs/openapi.yaml)
- [Integration Guide](../docs/INTEGRATION_GUIDE.md)
- [Stripe Refund API](https://stripe.com/docs/api/refunds)
- [Adyen Refund API](https://docs.adyen.com/api-explorer/#/CheckoutService/v70/post/payments/{paymentPspReference}/refunds)
- [Braintree Refund API](https://developers.braintreepayments.com/reference/request/transaction/refund)
- [Shopify Refund API](https://shopify.dev/docs/api/admin-rest/2024-07/resources/refund)

---

**Ready to deploy?** The Refund Orchestrator provides a production-ready, unified interface for provable refunds across all major PSPs! 🚀
