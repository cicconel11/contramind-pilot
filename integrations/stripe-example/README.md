# Stripe-Contramind Integration

This example demonstrates how to integrate Contramind decision certificates with Stripe payments and refunds.

## Features

- **Automated Refund Decisions**: Use Contramind to automatically approve/reject refunds
- **Charge Authorization**: Integrate decision making into payment processing
- **Certificate Verification**: Verify JWS certificates offline
- **Audit Trail**: Store decision certificates with Stripe metadata
- **Manual Review**: Handle HOLD_HUMAN decisions with manual review workflow

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your Stripe keys and Contramind URLs
   ```

3. **Start the server**:
   ```bash
   npm start
   ```

## API Endpoints

### POST /refund

Process a refund with Contramind decision making.

**Request**:
```json
{
  "charge_id": "ch_1234567890",
  "amount": 1000,
  "reason": "requested_by_customer"
}
```

**Response** (Auto-approved):
```json
{
  "success": true,
  "refund_id": "re_1234567890",
  "decision": "PASS",
  "proof_id": "abc123...",
  "certificate_jws": "eyJhbGciOiJFZERTQSIs...",
  "message": "Refund auto-approved"
}
```

**Response** (Manual review):
```json
{
  "success": true,
  "refund_id": "re_1234567890",
  "decision": "HOLD_HUMAN",
  "proof_id": "abc123...",
  "certificate_jws": "eyJhbGciOiJFZERTQSIs...",
  "message": "Refund created, manual review required"
}
```

### POST /charge

Process a charge with Contramind decision making.

**Request**:
```json
{
  "amount": 2000,
  "currency": "usd",
  "customer": "cus_1234567890",
  "metadata": {
    "country": "US",
    "recent_transactions": "3"
  }
}
```

### POST /verify

Verify a decision certificate offline.

**Request**:
```json
{
  "certificate_jws": "eyJhbGciOiJFZERTQSIs..."
}
```

**Response**:
```json
{
  "valid": true,
  "payload": {
    "sub": "decision",
    "decision": "PASS",
    "proof_id": "abc123..."
  },
  "header": {
    "alg": "EdDSA",
    "kid": "v1"
  }
}
```

## Decision Flow

### Refund Processing

1. **Receive refund request** with charge ID
2. **Retrieve original charge** from Stripe
3. **Extract decision inputs** (amount, country, customer history)
4. **Call Contramind** `/decide` endpoint
5. **Verify JWS certificate** offline
6. **Process based on decision**:
   - `PASS`: Auto-approve refund
   - `HOLD_HUMAN`: Create refund for manual review
   - `REJECT`: Deny refund

### Charge Processing

1. **Receive charge request** with payment details
2. **Extract decision inputs** from request
3. **Call Contramind** `/decide` endpoint
4. **Verify JWS certificate** offline
5. **Process based on decision**:
   - `PASS`: Create charge
   - `REJECT`: Deny charge

## Stripe Metadata

Decision certificates are stored in Stripe metadata:

```json
{
  "contramind_decision": "PASS",
  "contramind_proof_id": "abc123...",
  "contramind_certificate": "eyJhbGciOiJFZERTQSIs...",
  "contramind_param_hash": "def456...",
  "contramind_obligations": "[\"privacy_ok\",\"budget_ok\"]"
}
```

## Error Handling

- **Certificate verification failures** return 500 status
- **Decision rejections** return 403 status
- **Invalid requests** return 400 status
- **All errors** include decision certificate for audit

## Monitoring

### Key Metrics

- **Auto-approve rate**: % of decisions that are PASS
- **Manual review rate**: % of decisions that are HOLD_HUMAN
- **Verification failure rate**: % of certificate verification failures
- **Decision latency**: Time to get decision from Contramind

### Alerts

- Certificate verification failures > 0.1%
- Decision API errors > 1%
- High manual review rate > 20%

## Security

- **Always verify certificates** before trusting decisions
- **Store certificates** with transaction records
- **Use idempotency keys** for duplicate prevention
- **Monitor verification failures** for security issues

## Compliance

### SOC 2

- Cryptographic proof of decision authenticity
- Complete audit trail with timestamps
- Tamper-evident decision records

### PCI DSS

- Secure decision processing
- Cryptographic protection of decision data
- Audit trail for payment decisions

## Testing

### Test Refund

```bash
curl -X POST http://localhost:3000/refund \
  -H "Content-Type: application/json" \
  -d '{
    "charge_id": "ch_test_123",
    "amount": 1000,
    "reason": "requested_by_customer"
  }'
```

### Test Charge

```bash
curl -X POST http://localhost:3000/charge \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 2000,
    "currency": "usd",
    "customer": "cus_test_123",
    "metadata": {
      "country": "US",
      "recent_transactions": "3"
    }
  }'
```

### Test Verification

```bash
curl -X POST http://localhost:3000/verify \
  -H "Content-Type: application/json" \
  -d '{
    "certificate_jws": "eyJhbGciOiJFZERTQSIs..."
  }'
```

## Production Deployment

1. **Use production Stripe keys**
2. **Configure production Contramind URLs**
3. **Set up monitoring and alerting**
4. **Implement proper error handling**
5. **Configure rate limiting**
6. **Set up log aggregation**
