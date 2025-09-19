# TEE/ZK Attestation Roadmap

## Overview

The current attestor service uses Ed25519 signatures for decision attestation. This roadmap outlines how to extend the system to support Trusted Execution Environments (TEE) and Zero-Knowledge (ZK) proofs while maintaining API compatibility.

## Current Architecture

```
Client -> Kernel -> Attestor -> {signature_b64, public_key_b64, digest_hex, kid}
```

## TEE Integration

### AWS Nitro Enclaves
- **Attestation Document**: Nitro Enclave generates attestation document with PCRs
- **API Extension**: Add `tee_report` field to response
- **Verification**: Check both Ed25519 signature and TEE attestation document

### Intel SGX
- **Quote Generation**: SGX enclave generates quote with measurements
- **API Extension**: Add `sgx_quote` field to response
- **Verification**: Verify quote against Intel's attestation service

### AMD SEV
- **Attestation Report**: SEV generates attestation report with measurements
- **API Extension**: Add `sev_report` field to response
- **Verification**: Verify report against AMD's attestation service

### Implementation Plan

1. **Phase 1: TEE Mode Detection**
   ```python
   # Add mode parameter to attestor
   ATTESTOR_MODE = os.getenv("ATTESTOR_MODE", "ed25519")  # ed25519|tee|zk
   ```

2. **Phase 2: TEE Response Format**
   ```json
   {
     "signature_b64": "...",
     "public_key_b64": "...",
     "digest_hex": "...",
     "kid": "tee:v1",
     "mode": "tee",
     "evidence": {
       "tee_type": "nitro|sgx|sev",
       "attestation_document": "...",
       "pcr_values": {...},
       "measurements": {...}
     }
   }
   ```

3. **Phase 3: Verification Logic**
   ```python
   def verify_tee_attestation(response):
       # Verify Ed25519 signature
       verify_ed25519_signature(response)
       
       # Verify TEE attestation
       if response["mode"] == "tee":
           verify_tee_evidence(response["evidence"])
   ```

## ZK Proof Integration

### Succinct Proofs
- **Proof Generation**: Generate ZK proof of decision computation
- **API Extension**: Add `proof` field to response
- **Verification**: Verify proof against published verifying key

### Implementation Plan

1. **Phase 1: ZK Mode Detection**
   ```python
   ATTESTOR_MODE = os.getenv("ATTESTOR_MODE", "ed25519")  # ed25519|tee|zk
   ```

2. **Phase 2: ZK Response Format**
   ```json
   {
     "proof": "...",
     "vk_id": "zk:v1",
     "digest_hex": "...",
     "mode": "zk",
     "evidence": {
       "proof_type": "groth16|plonk|stark",
       "public_inputs": [...],
       "verifying_key_hash": "..."
     }
   }
   ```

3. **Phase 3: Verification Logic**
   ```python
   def verify_zk_proof(response):
       if response["mode"] == "zk":
           verify_zk_proof(response["proof"], response["evidence"])
   ```

## Migration Strategy

### Backward Compatibility
- Keep existing Ed25519 mode as default
- Add mode parameter to control attestation method
- Maintain same bundle hashing for consistency

### Gradual Rollout
1. **Development**: Implement TEE/ZK modes alongside Ed25519
2. **Testing**: Run all modes in parallel for validation
3. **Production**: Gradually migrate to TEE/ZK modes
4. **Deprecation**: Eventually deprecate Ed25519 mode

### Configuration
```yaml
# docker-compose.yml
attestor:
  environment:
    ATTESTOR_MODE: "tee"  # ed25519|tee|zk
    TEE_TYPE: "nitro"     # nitro|sgx|sev
    ZK_PROOF_TYPE: "groth16"  # groth16|plonk|stark
```

## Security Considerations

### TEE Security
- **Attestation Verification**: Always verify TEE attestation documents
- **Key Management**: Use TEE-protected keys when possible
- **Network Security**: Ensure secure communication with TEE

### ZK Security
- **Trusted Setup**: Use secure trusted setup ceremonies
- **Verifying Keys**: Publish and verify verifying key hashes
- **Proof Verification**: Implement robust proof verification

## Performance Considerations

### TEE Performance
- **Enclave Startup**: TEE enclaves have startup overhead
- **Memory Constraints**: Limited memory in TEE environments
- **Network Latency**: Additional latency for attestation verification

### ZK Performance
- **Proof Generation**: ZK proofs are computationally expensive
- **Proof Size**: Proofs can be large (several KB)
- **Verification Time**: Proof verification has overhead

## Monitoring and Observability

### Metrics
- Attestation mode distribution
- TEE attestation success/failure rates
- ZK proof generation/verification times
- Evidence verification latency

### Alerts
- TEE attestation failures
- ZK proof generation failures
- Evidence verification failures
- Performance degradation

## Implementation Timeline

### Q1: TEE Foundation
- Implement TEE mode detection
- Add basic TEE response format
- Implement AWS Nitro Enclaves support

### Q2: TEE Expansion
- Add Intel SGX support
- Add AMD SEV support
- Implement TEE verification logic

### Q3: ZK Foundation
- Implement ZK mode detection
- Add basic ZK response format
- Implement Groth16 proof support

### Q4: ZK Expansion
- Add PLONK support
- Add STARK support
- Implement ZK verification logic

## Success Metrics

- **Security**: Zero attestation bypasses
- **Performance**: <2x latency increase for TEE/ZK modes
- **Reliability**: 99.9% attestation success rate
- **Adoption**: Gradual migration from Ed25519 to TEE/ZK

## Conclusion

This roadmap provides a clear path to extend the attestor service with TEE and ZK capabilities while maintaining backward compatibility and API consistency. The phased approach allows for gradual implementation and testing of each component.
