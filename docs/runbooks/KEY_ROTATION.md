# Key Rotation Runbook

## Overview
This runbook describes the process for rotating attestor keys in the Contramind system.

## Prerequisites
- Access to the production environment
- Understanding of the current key configuration
- Backup of current keys (for rollback if needed)

## Key Rotation Process

### 1. Add New Key
```bash
# Add new key to ATTESTOR_KEYS environment variable
# Format: "ed25519:v1:seed1;ed25519:v2:seed2;ed25519:v3:new-seed"
```

### 2. Deploy with New Key
```bash
# Update docker-compose.yml or environment variables
# Deploy the updated configuration
make prod
```

### 3. Monitor Verification Success
```bash
# Monitor /verify endpoint success with old key for N days
# Check logs for verification failures
docker compose logs attestor | grep "verify"
```

### 4. Switch Active Key
```bash
# Update ATTESTOR_ACTIVE_KID to new key
# Deploy the change
make prod
```

### 5. Remove Old Key
```bash
# After N days of successful operation with new key
# Remove old key from ATTESTOR_KEYS
# Deploy final configuration
make prod
```

## Verification Steps

### Check Key Status
```bash
# List available keys
curl -s localhost:8082/keys | jq

# Check active key
curl -s localhost:8082/keys | jq .active
```

### Test Signing
```bash
# Test signing with new key
curl -s -X POST localhost:8082/sign \
  -H 'content-type: application/json' \
  -d '{"bundle":{"test":"rotation"}}' | jq .kid
```

### Test Verification
```bash
# Test verification with new key
SIG=$(curl -s -X POST localhost:8082/sign \
  -H 'content-type: application/json' \
  -d '{"bundle":{"test":"rotation"}}')

curl -s -X POST localhost:8082/verify \
  -H 'content-type: application/json' \
  -d "$SIG" | jq .valid
```

## Rollback Procedure

### If Issues Occur
```bash
# Revert ATTESTOR_ACTIVE_KID to previous key
# Deploy the rollback
make prod

# Verify system is working
./smoke-test.sh
```

## Monitoring

### Key Metrics
- Signature success rate
- Verification success rate
- Key usage distribution
- Error rates by key

### Alerts
- Signature failures
- Verification failures
- Key rotation completion
- Rollback events

## Best Practices

1. **Gradual Rollout**: Rotate keys during low-traffic periods
2. **Monitoring**: Monitor system health during rotation
3. **Backup**: Keep old keys for rollback capability
4. **Testing**: Test rotation in staging environment first
5. **Documentation**: Document all key changes

## Troubleshooting

### Common Issues
- **Key Not Found**: Check ATTESTOR_KEYS format
- **Verification Failures**: Ensure old keys are still available
- **Performance Issues**: Monitor system resources during rotation

### Recovery Steps
1. Check service logs
2. Verify environment variables
3. Test individual components
4. Rollback if necessary
