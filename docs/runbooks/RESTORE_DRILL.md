# Restore Drill Runbook

## Overview
This runbook describes the process for restoring the Contramind system from backup in case of data loss or corruption.

## Prerequisites
- Access to the production environment
- Latest database backup file
- Understanding of the system architecture
- Test environment for validation

## Restore Process

### 1. Provision Empty Postgres
```bash
# Stop all services
make down

# Remove existing postgres data (if needed)
docker volume rm contramind-pilot_pgdata

# Start only postgres
docker compose up -d postgres

# Wait for postgres to be ready
docker compose logs postgres | grep "ready to accept connections"
```

### 2. Run Schema SQLs
```bash
# The schema will be automatically applied via init scripts
# Check that all tables are created
docker exec -it cm-postgres psql -U cm -d cm -c "\dt cm.*"
```

### 3. Restore from Backup
```bash
# Find the latest backup
ls -la ops/backups/ | head -5

# Restore from backup
docker exec -i cm-postgres psql -U cm -d cm < ops/backups/cm_YYYY-MM-DD_HHMMSS.sql
```

### 4. Bring Up Services
```bash
# Start all services
make up

# Wait for services to be healthy
docker compose ps
```

### 5. Run Smoke Test
```bash
# Verify system functionality
./smoke-test.sh
```

### 6. Run Replay Test
```bash
# Check for decision drift
python3 tools/replay.py
```

## Verification Steps

### Database Integrity
```bash
# Check table counts
docker exec -it cm-postgres psql -U cm -d cm -c "
SELECT 
  schemaname,
  tablename,
  n_tup_ins as inserts,
  n_tup_upd as updates,
  n_tup_del as deletes
FROM pg_stat_user_tables 
WHERE schemaname = 'cm';"
```

### Service Health
```bash
# Check all services are running
docker compose ps

# Check service logs for errors
docker compose logs --since=5m
```

### Decision Ledger
```bash
# Check decision ledger integrity
docker exec -it cm-postgres psql -U cm -d cm -c "
SELECT 
  COUNT(*) as total_decisions,
  COUNT(DISTINCT proof_id) as unique_proofs,
  MIN(ts) as earliest_decision,
  MAX(ts) as latest_decision
FROM cm.decision_ledger;"
```

## Recovery Validation

### Functional Tests
```bash
# Test decision making
curl -s -X POST localhost:8081/verify \
  -H 'content-type: application/json' \
  -d '{"type":"issuer_verify"}' | jq

# Test attestation
curl -s -X POST localhost:8082/sign \
  -H 'content-type: application/json' \
  -d '{"bundle":{"test":"restore"}}' | jq

# Test control plane
curl -s -H "Authorization: Bearer changeme" \
  localhost:8083/param/hash | jq
```

### Performance Tests
```bash
# Run load test
docker run --rm -i --network=host grafana/k6 run - < ops/k6-decide.js
```

## Troubleshooting

### Common Issues
- **Schema Errors**: Check init scripts are correct
- **Data Corruption**: Verify backup file integrity
- **Service Failures**: Check service logs and dependencies
- **Performance Issues**: Monitor system resources

### Recovery Steps
1. Check service logs
2. Verify database connectivity
3. Test individual components
4. Check network connectivity
5. Validate configuration

## Post-Recovery Tasks

### Monitoring
- Verify all metrics are being collected
- Check alert rules are working
- Validate log aggregation

### Documentation
- Document the recovery process
- Update incident reports
- Review backup procedures

### Testing
- Run full test suite
- Perform load testing
- Validate all integrations

## Prevention

### Backup Strategy
- Daily automated backups
- Test backup restoration monthly
- Store backups in multiple locations
- Verify backup integrity

### Monitoring
- Database health checks
- Service availability monitoring
- Performance monitoring
- Alert on anomalies

## Emergency Contacts

### Escalation Path
1. On-call engineer
2. Team lead
3. Engineering manager
4. CTO

### Communication
- Incident channel
- Status page updates
- Customer notifications
- Post-incident review
