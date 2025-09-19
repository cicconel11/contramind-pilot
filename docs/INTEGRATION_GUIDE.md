# Contramind Integration Guide

## 🚀 Production-Ready Reference Integrations

This guide provides complete, production-ready integrations for the Contramind Decision API with JWS certificates.

## 📦 Available SDKs

### Node.js SDK
- **Location**: `integrations/node-sdk/`
- **Features**: JWS verification, idempotency, Express middleware
- **Dependencies**: `undici`, `jose`
- **Status**: ✅ Tested and working

### Python SDK  
- **Location**: `integrations/python-sdk/`
- **Features**: JWS verification, Pydantic models, Stripe extractors
- **Dependencies**: `requests`, `pynacl`, `pydantic`
- **Status**: ✅ Tested and working

## 🏪 Stripe Integration Example

### Complete Refund/Charge Processing
- **Location**: `integrations/stripe-example/`
- **Features**: 
  - Automated refund decisions
  - Charge authorization
  - Certificate verification
  - Audit trail with Stripe metadata
- **Status**: ✅ Ready for production

## 📋 Decision Certificate Specification

### JWS Format
- **Algorithm**: EdDSA (Ed25519)
- **Structure**: `header.payload.signature`
- **Verification**: Offline with public keys from `/keys` endpoint

### Payload Schema
```json
{
  "sub": "decision",
  "ts": "2025-09-17T03:14:00Z",
  "decision": "PASS | HOLD_HUMAN | REJECT | NEED_ONE_BIT",
  "kernel_id": "K_demo_v1",
  "param_hash": "c058…",
  "inputs": { "amount": 2750.0, "country": "US", "recent": 2 },
  "obligations": ["privacy_ok","budget_ok"],
  "proof_id": "e693ac0…"
}
```

## 🔧 Quick Start

### 1. Node.js Integration

```javascript
import ContramindDecider from '@contramind/decider-sdk';

const decider = new ContramindDecider({
  deciderUrl: 'http://localhost:8084',
  attestorUrl: 'http://localhost:8082'
});

// Make a decision
const result = await decider.decide({
  amount: 1500.0,
  country: 'US',
  ts: new Date().toISOString(),
  recent: 1,
  context_id: 'order-12345'
});

console.log('Decision:', result.decision);
console.log('Verified:', result.verified);
console.log('Certificate:', result.certificate_jws);
```

### 2. Python Integration

```python
from contramind import ContramindDecider

decider = ContramindDecider(
    decider_url="http://localhost:8084",
    attestor_url="http://localhost:8082"
)

# Make a decision
result = decider.decide({
    "amount": 1500.0,
    "country": "US",
    "ts": "2025-09-16T12:00:00Z",
    "recent": 1,
    "context_id": "order-12345"
})

print(f"Decision: {result.decision}")
print(f"Verified: {result.verified}")
print(f"Certificate: {result.certificate_jws}")
```

### 3. Stripe Integration

```javascript
// Process refund with decision
app.post('/refund', async (req, res) => {
  const { charge_id, amount } = req.body;
  
  // Get decision
  const decision = await makeDecision({
    amount: amount / 100,
    country: 'US',
    ts: new Date().toISOString(),
    recent: 0,
    context_id: `stripe_refund:${charge_id}`
  });
  
  if (decision.decision === 'PASS') {
    // Auto-approve refund
    const refund = await stripe.refunds.create({
      charge: charge_id,
      amount: amount,
      metadata: {
        contramind_decision: decision.decision,
        contramind_certificate: decision.certificate_jws,
        contramind_proof_id: decision.proof_id
      }
    });
    
    res.json({ success: true, refund_id: refund.id });
  } else {
    res.status(403).json({ 
      success: false, 
      decision: decision.decision 
    });
  }
});
```

## 🎯 High-Impact Use Cases

### 1. Refund Automation (>$1k)
- **ROI**: Reduce manual reviews by 80%
- **Implementation**: Stripe webhook + decision API
- **Benefits**: Faster processing, fewer disputes, audit trail

### 2. Data Export Gates
- **ROI**: SOC2/GDPR compliance automation
- **Implementation**: Export button + decision API
- **Benefits**: Provable approvals, audit compliance

### 3. Deploy Guards
- **ROI**: Provable change approvals
- **Implementation**: CI job + decision API
- **Benefits**: Risk-based deployments, audit trail

## 📊 Key Performance Indicators

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

## 🚀 Production Deployment

### Environment Setup
```bash
# Development
CONTRAMIND_DECIDER_URL=http://localhost:8084
CONTRAMIND_ATTESTOR_URL=http://localhost:8082

# Production
CONTRAMIND_DECIDER_URL=https://api.contramind.com
CONTRAMIND_ATTESTOR_URL=https://attestor.contramind.com
```

### Health Checks
```bash
# Check decision API
curl http://localhost:8084/healthz

# Check attestor
curl http://localhost:8082/keys
```

### Error Handling
- Implement retry logic for transient failures
- Handle certificate verification failures gracefully
- Monitor decision API availability
- Set up alerting for critical failures

## 📈 Scaling Considerations

### Performance
- Use connection pooling for database connections
- Cache public keys locally
- Implement request batching where possible
- Monitor decision latency

### Reliability
- Implement circuit breakers for external calls
- Use idempotency keys for duplicate prevention
- Store decisions locally for offline verification
- Implement graceful degradation

## 🔄 Shadow Mode Rollout

### Phase 1: Shadow Mode
- Log decisions without acting on them
- Compare to existing process
- Measure accuracy and performance
- Build confidence in the system

### Phase 2: Gradual Rollout
- Start with 10% of traffic
- Monitor decision quality
- Gradually increase to 100%
- Maintain fallback mechanisms

### Phase 3: Full Enforcement
- Remove fallback mechanisms
- Optimize for performance
- Implement advanced features
- Scale to full production load

## 📚 Additional Resources

- [Decision Certificate Specification](DECISION_CERTIFICATE_SPEC.md)
- [OpenAPI Specification](openapi.yaml)
- [Stripe Integration Example](../integrations/stripe-example/)
- [Node.js SDK](../integrations/node-sdk/)
- [Python SDK](../integrations/python-sdk/)

## 🆘 Support

For integration support:
- Check the [OpenAPI spec](openapi.yaml) for API details
- Review the [Decision Certificate spec](DECISION_CERTIFICATE_SPEC.md) for JWS format
- Test with the provided SDK examples
- Monitor the health endpoints for service status

---

**Ready to integrate?** Start with the Stripe example for the fastest ROI on refund automation! 🎯
