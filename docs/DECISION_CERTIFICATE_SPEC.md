# Contramind Decision Certificate Specification

## Overview

Contramind Decision Certificates are JWS (JSON Web Signature) tokens that provide cryptographic proof of decision authenticity and integrity. They enable offline verification and audit trails for all decisions made by the Contramind system.

## Format

- **Type**: JWS (JSON Web Signature) - Compact Serialization
- **Algorithm**: EdDSA (Ed25519)
- **Structure**: `header.payload.signature`

## Header

```json
{
  "alg": "EdDSA",
  "kid": "v1",
  "typ": "JWT"
}
```

### Fields

- `alg`: Always "EdDSA" (Ed25519 signature algorithm)
- `kid`: Key identifier for the signing key (e.g., "v1", "v2")
- `typ`: Always "JWT" (JSON Web Token)

## Payload

```json
{
  "sub": "decision",
  "ts": "2025-09-17T03:14:00Z",
  "decision": "PASS",
  "kernel_id": "K_demo_v1_2750_allowlist",
  "param_hash": "c058c1aa59bacd6e6bbf8030e1fb57e2",
  "inputs": {
    "amount": 2750.0,
    "country": "US",
    "recent": 2
  },
  "obligations": ["privacy_ok", "budget_ok"],
  "proof_id": "e693ac0f8b2d4c5a9e1f7a3b6c8d2e4f5a7b9c1d3e5f7a9b1c3d5e7f9a1b3c5d7"
}
```

### Fields

- `sub`: Subject - always "decision"
- `ts`: ISO 8601 timestamp of decision
- `decision`: Decision outcome - one of:
  - `"PASS"`: Transaction approved
  - `"HOLD_HUMAN"`: Requires manual review
  - `"REJECT"`: Transaction rejected
  - `"NEED_ONE_BIT"`: Requires additional verification
- `kernel_id`: Identifier of the decision kernel used
- `param_hash`: SHA-256 hash of parameters used in decision
- `inputs`: Original decision inputs
  - `amount`: Transaction amount (decimal)
  - `country`: ISO country code
  - `recent`: Number of recent transactions
- `obligations`: List of obligations/requirements met
- `proof_id`: SHA-256 hash of canonical decision + signature (tamper evidence)

## Verification Process

### 1. Parse JWS

Split the JWS into three parts: `header.payload.signature`

### 2. Decode Header

```javascript
const header = JSON.parse(base64urlDecode(headerPart));
```

### 3. Fetch Public Key

```javascript
const keysResponse = await fetch(`${ATTESTOR_URL}/keys`);
const keys = await keysResponse.json();
const publicKey = keys.keys[header.kid];
```

### 4. Verify Signature

```javascript
const verifyKey = new VerifyKey(base64Decode(publicKey));
verifyKey.verify(
  Buffer.from(headerPart + "." + payloadPart),
  base64urlDecode(signaturePart)
);
```

### 5. Decode Payload

```javascript
const payload = JSON.parse(base64urlDecode(payloadPart));
```

## Implementation Examples

### Node.js (using jose library)

```javascript
import { createRemoteJWKSet, jwtVerify } from "jose";

const JWKS = createRemoteJWKSet(new URL("http://localhost:8082/keys"));

async function verifyCertificate(jws) {
  const { payload, protectedHeader } = await jwtVerify(jws, JWKS, {
    algorithms: ["EdDSA"],
  });
  return payload;
}
```

### Python (using PyNaCl)

```python
import base64
import json
import requests
from nacl.signing import VerifyKey

def verify_jws(jws: str, attestor_url: str = "http://localhost:8082"):
    h, p, s = jws.split(".")
    header = json.loads(base64.urlsafe_b64decode(h + "=="))
    kid = header["kid"]
    
    keys = requests.get(f"{attestor_url}/keys").json()["keys"]
    vk = VerifyKey(base64.b64decode(keys[kid]))
    vk.verify((h + "." + p).encode(), base64.urlsafe_b64decode(s + "=="))
    
    return json.loads(base64.urlsafe_b64decode(p + "=="))
```

## Security Considerations

### Key Management

- Keys are managed by the Attestor service
- Multiple keys supported for rotation
- Key identifiers (kid) track which key was used
- Public keys available via `/keys` endpoint

### Tamper Evidence

- `proof_id` provides tamper evidence
- Calculated as: `SHA256(canonical_decision + signature)`
- Any modification invalidates the proof_id
- Enables detection of certificate tampering

### Replay Protection

- Timestamps prevent replay attacks
- Idempotency keys prevent duplicate processing
- Context IDs provide additional tracking

## Audit Trail

### Decision Ledger

All decisions are stored in the `cm.decision_ledger` table with:

- `proof_id`: Tamper-evident identifier
- `certificate_jws`: Complete JWS certificate
- `idempotency_key`: Prevents duplicate processing
- `bundle`: Complete decision context
- `ts`: Timestamp of decision

### Verification

- Certificates can be verified offline
- No need to call Contramind services
- Enables independent audit and compliance
- Supports regulatory requirements

## Compliance

### SOC 2

- Cryptographic proof of decision authenticity
- Complete audit trail with timestamps
- Tamper-evident decision records
- Independent verification capability

### GDPR

- Decision transparency and explainability
- Right to explanation compliance
- Audit trail for data processing decisions
- Cryptographic integrity guarantees

### PCI DSS

- Secure decision processing
- Cryptographic protection of decision data
- Audit trail for payment decisions
- Tamper detection capabilities

## Integration Guidelines

### Best Practices

1. **Always verify certificates** before trusting decisions
2. **Store certificates** with transaction records
3. **Use idempotency keys** for duplicate prevention
4. **Monitor verification failures** (< 0.1% SLO)
5. **Implement key rotation** support

### Error Handling

- Handle verification failures gracefully
- Log verification errors for monitoring
- Implement fallback mechanisms
- Alert on high verification failure rates

### Performance

- Cache public keys locally
- Implement connection pooling
- Monitor verification latency
- Set appropriate timeouts

## Version History

- **v1.0.0**: Initial specification with EdDSA signatures
- **v1.1.0**: Added proof_id for tamper evidence
- **v1.2.0**: Added obligations field
- **v1.3.0**: Added context_id support

## References

- [RFC 7515 - JSON Web Signature (JWS)](https://tools.ietf.org/html/rfc7515)
- [RFC 8037 - CFRG Elliptic Curve Diffie-Hellman (ECDH) and Signatures in JSON Object Signing and Encryption (JOSE)](https://tools.ietf.org/html/rfc8037)
- [Ed25519 Signature Algorithm](https://ed25519.cr.yp.to/)
