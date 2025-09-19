# Contramind PSP Refund Integrations

Production-ready refund integrations for major payment service providers (PSPs) with Contramind decision certificates.

## 🏪 Supported PSPs

- **Stripe** - Metadata-based proof storage
- **Adyen** - Webhook-based reconciliation  
- **Braintree** - Custom fields and database storage
- **Shopify** - Metafields and order notes

## 🚀 Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

```bash
# Stripe
export STRIPE_SECRET_KEY="sk_test_..."

# Adyen  
export ADYEN_API_KEY="AQE..."
export ADYEN_MERCHANT_ACCOUNT="YourMerchantAccount"
export ADYEN_ENVIRONMENT="test"

# Braintree
export BRAINTREE_MERCHANT_ID="your_merchant_id"
export BRAINTREE_PUBLIC_KEY="your_public_key"
export BRAINTREE_PRIVATE_KEY="your_private_key"
export BRAINTREE_ENVIRONMENT="sandbox"

# Shopify
export SHOPIFY_SHOP="your-shop"
export SHOPIFY_ACCESS_TOKEN="shpat_..."
export SHOPIFY_API_VERSION="2024-07"

# Contramind
export CONTRAMIND_DECIDER_URL="http://localhost:8084"
export CONTRAMIND_ATTESTOR_URL="http://localhost:8082"
```

### 3. Test the Integration

```bash
# Test all PSP integrations
npm test

# Test certificate verification
node verify-cert.js "eyJhbGciOiJFZERTQSIs..."
```

## 📋 Usage Examples

### Stripe Refund

```javascript
import { refundStripe } from './stripe.js';

const result = await refundStripe({
  chargeId: "ch_1234567890",
  amountMinor: 1500, // $15.00
  currency: "USD",
  customerCountry: "US",
  customerId: "cus_1234567890"
});

if (result.success) {
  console.log("Refund created:", result.refund_id);
  console.log("Decision certificate:", result.certificate_jws);
}
```

### Adyen Refund

```javascript
import { refundAdyen } from './adyen.js';

const result = await refundAdyen({
  paymentPspReference: "8515131751004933",
  amountMinor: 1500,
  currency: "USD",
  customerCountry: "US"
});

if (result.success) {
  console.log("Refund initiated:", result.refund_psp_reference);
}
```

### Braintree Refund

```javascript
import { refundBraintree } from './braintree.js';

const result = await refundBraintree({
  originalTransactionId: "abc123def456",
  amountMinor: 1500,
  currency: "USD"
});

if (result.success) {
  console.log("Refund created:", result.refund_transaction_id);
}
```

### Shopify Refund

```javascript
import { refundShopify } from './shopify.js';

const result = await refundShopify({
  orderId: "1234567890",
  amountMinor: 1500,
  currency: "USD",
  refundLineItems: [{
    lineItemId: "1234567890",
    quantity: 1,
    restockType: "return"
  }]
});

if (result.success) {
  console.log("Refund created:", result.refund_id);
}
```

## 🔐 Certificate Verification

### Node.js

```javascript
import { verifyCertificate } from './verify-cert.js';

const result = await verifyCertificate(certificateJws);
if (result.valid) {
  console.log("Decision:", result.payload.decision);
  console.log("Proof ID:", result.payload.proof_id);
}
```

### Python

```bash
python verify-cert.py "eyJhbGciOiJFZERTQSIs..."
```

### Command Line

```bash
node verify-cert.js "eyJhbGciOiJFZERTQSIs..."
```

## 🏗️ Express.js Integration

```javascript
import express from 'express';
import { 
  createStripeRefundEndpoint,
  createAdyenRefundEndpoint,
  createBraintreeRefundEndpoint,
  createShopifyRefundEndpoint
} from './index.js';

const app = express();
app.use(express.json());

// PSP refund endpoints
app.post('/refunds/stripe', createStripeRefundEndpoint);
app.post('/refunds/adyen', createAdyenRefundEndpoint);
app.post('/refunds/braintree', createBraintreeRefundEndpoint);
app.post('/refunds/shopify', createShopifyRefundEndpoint);

app.listen(3000, () => {
  console.log('PSP refund service running on port 3000');
});
```

## 📊 Decision Flow

### 1. Refund Request
- Extract PSP reference (charge ID, payment reference, etc.)
- Get customer context (country, recent refunds)
- Generate idempotency key

### 2. Contramind Decision
- Call `/decide` endpoint with refund context
- Receive decision: `PASS`, `HOLD_HUMAN`, `REJECT`, or `NEED_ONE_BIT`
- Get JWS certificate for offline verification

### 3. PSP Refund Creation
- **PASS**: Create refund with decision metadata
- **HOLD_HUMAN**: Queue for manual review
- **REJECT**: Deny refund request

### 4. Certificate Storage
- Store full JWS certificate in your database
- Store proof ID and key ID in PSP metadata
- Link refund to decision for audit trail

## 🔄 Webhook Handling

### Adyen Webhooks

```javascript
import { handleAdyenRefundWebhook } from './adyen.js';

app.post('/webhooks/adyen', handleAdyenRefundWebhook);
```

### Braintree Webhooks

```javascript
import { handleBraintreeWebhook } from './braintree.js';

app.post('/webhooks/braintree', handleBraintreeWebhook);
```

### Shopify Webhooks

```javascript
import { handleShopifyWebhook } from './shopify.js';

app.post('/webhooks/shopify', handleShopifyWebhook);
```

## 🗄️ Database Schema

### Refund Decisions Table

```sql
CREATE TABLE refund_decisions (
  id SERIAL PRIMARY KEY,
  psp VARCHAR(20) NOT NULL,
  psp_ref VARCHAR(255) NOT NULL,
  amount_minor INTEGER NOT NULL,
  currency VARCHAR(3) NOT NULL,
  decision VARCHAR(20) NOT NULL,
  proof_id VARCHAR(64) NOT NULL,
  kid VARCHAR(50) NOT NULL,
  param_hash VARCHAR(64) NOT NULL,
  certificate_jws TEXT NOT NULL,
  idempotency_key VARCHAR(255) UNIQUE NOT NULL,
  stripe_refund_id VARCHAR(255),
  adyen_refund_reference VARCHAR(255),
  braintree_refund_id VARCHAR(255),
  shopify_refund_id VARCHAR(255),
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP
);

CREATE INDEX idx_refund_decisions_psp_ref ON refund_decisions(psp, psp_ref);
CREATE INDEX idx_refund_decisions_proof_id ON refund_decisions(proof_id);
CREATE INDEX idx_refund_decisions_idempotency ON refund_decisions(idempotency_key);
```

## 🚦 Rollout Strategy

### Phase 1: Shadow Mode (1-2 days)
- Call Contramind for all refunds
- Store decisions and certificates
- Log decisions but don't act on them
- Compare to existing process

### Phase 2: Warn Mode (1-2 days)
- Block refunds when decision is `REJECT`
- Log `HOLD_HUMAN` decisions for manual review
- Monitor decision accuracy

### Phase 3: Full Enforcement
- Gate all refunds on Contramind decisions
- Tune parameters via Control Plane
- Monitor SLOs and dispute rates

## 📈 Key Metrics

### Success Metrics
- **Auto-approve rate**: Target >70% for refunds
- **Verification failure rate**: Target <0.1%
- **Decision latency**: Target <500ms p95
- **Dispute win rate**: Target >95% with certificates

### Monitoring
- Certificate verification failures
- Decision API errors  
- Manual review rates
- Decision latency percentiles
- PSP refund success rates

## 🔒 Security Best Practices

### Certificate Verification
- Always verify JWS certificates before trusting decisions
- Cache public keys locally for performance
- Monitor verification failure rates
- Implement fallback mechanisms

### Key Management
- Support key rotation (multiple `kid` values)
- Monitor key expiration
- Implement key validation
- Use secure key storage

### Audit Trail
- Store certificates with transaction records
- Log all decision requests and responses
- Monitor for certificate tampering
- Implement decision replay capabilities

## 🆘 Troubleshooting

### Common Issues

**Decision API Unavailable**
- Check Contramind services are running
- Verify network connectivity
- Implement circuit breakers

**Certificate Verification Fails**
- Check attestor service is running
- Verify key ID exists in `/keys` endpoint
- Ensure JWS format is correct

**PSP Refund Fails**
- Check PSP credentials and permissions
- Verify refund amount and currency
- Check PSP-specific error messages

### Debug Commands

```bash
# Check Contramind services
curl http://localhost:8084/healthz
curl http://localhost:8082/keys

# Test decision API
curl -X POST http://localhost:8084/decide \
  -H "Content-Type: application/json" \
  -d '{"amount":15.0,"country":"US","ts":"2025-09-16T12:00:00Z","recent":0}'

# Verify certificate
node verify-cert.js "your-jws-here"
```

## 📚 Additional Resources

- [Decision Certificate Specification](../../docs/DECISION_CERTIFICATE_SPEC.md)
- [OpenAPI Specification](../../docs/openapi.yaml)
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md)
- [Stripe Refund API](https://stripe.com/docs/api/refunds)
- [Adyen Refund API](https://docs.adyen.com/api-explorer/#/CheckoutService/v70/post/payments/{paymentPspReference}/refunds)
- [Braintree Refund API](https://developers.braintreepayments.com/reference/request/transaction/refund)
- [Shopify Refund API](https://shopify.dev/docs/api/admin-rest/2024-07/resources/refund)

---

**Ready to integrate?** Start with shadow mode to build confidence, then gradually roll out to production! 🚀
