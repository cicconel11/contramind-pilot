# Schema Changes Runbook

## Overview
This runbook describes the process for making database schema changes in the Contramind system.

## Prerequisites
- Access to the production environment
- Understanding of the current schema
- Backup of current database
- Test environment for validation

## Schema Change Process

### 1. Create Migration Script
```bash
# Create new migration file
# Format: db/init/00X_description.sql
# Example: db/init/004_add_audit_log.sql
```

### 2. Update Schema Version
```sql
-- Add to migration script
CREATE TABLE IF NOT EXISTS cm.schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ DEFAULT now(),
  description TEXT
);

-- Insert new version
INSERT INTO cm.schema_version (version, description) 
VALUES (4, 'Add audit log table');
```

### 3. Test in Staging
```bash
# Deploy to staging environment
# Run migration
# Validate changes
# Run test suite
```

### 4. Backup Production
```bash
# Create backup before migration
./ops/backup.sh
```

### 5. Deploy Migration
```bash
# Deploy new version
make prod

# Verify migration applied
docker exec -it cm-postgres psql -U cm -d cm -c "
SELECT version, applied_at, description 
FROM cm.schema_version 
ORDER BY version DESC;"
```

### 6. Validate Changes
```bash
# Run smoke test
./smoke-test.sh

# Check for errors
docker compose logs postgres | grep -i error
```

## Migration Best Practices

### Backward Compatibility
- Add new columns as nullable
- Use ALTER TABLE ADD COLUMN
- Avoid dropping columns immediately
- Use views for complex changes

### Performance Considerations
- Add indexes after data migration
- Use CONCURRENTLY for large tables
- Monitor query performance
- Test with production data volume

### Rollback Strategy
- Keep rollback scripts ready
- Test rollback procedures
- Document rollback steps
- Have backup restoration plan

## Example Migration

### Adding Audit Log Table
```sql
-- db/init/004_add_audit_log.sql
CREATE TABLE IF NOT EXISTS cm.audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  user_id TEXT,
  action TEXT NOT NULL,
  resource_type TEXT,
  resource_id TEXT,
  old_values JSONB,
  new_values JSONB,
  ip_address INET,
  user_agent TEXT
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON cm.audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON cm.audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON cm.audit_log(action);

-- Update schema version
INSERT INTO cm.schema_version (version, description) 
VALUES (4, 'Add audit log table');
```

## Validation Steps

### Schema Validation
```bash
# Check table structure
docker exec -it cm-postgres psql -U cm -d cm -c "\d cm.audit_log"

# Check indexes
docker exec -it cm-postgres psql -U cm -d cm -c "\di cm.*audit*"

# Check constraints
docker exec -it cm-postgres psql -U cm -d cm -c "
SELECT conname, contype, confrelid::regclass 
FROM pg_constraint 
WHERE conrelid = 'cm.audit_log'::regclass;"
```

### Data Validation
```bash
# Check data integrity
docker exec -it cm-postgres psql -U cm -d cm -c "
SELECT 
  COUNT(*) as total_records,
  COUNT(DISTINCT user_id) as unique_users,
  MIN(ts) as earliest_record,
  MAX(ts) as latest_record
FROM cm.audit_log;"
```

### Performance Validation
```bash
# Check query performance
docker exec -it cm-postgres psql -U cm -d cm -c "
EXPLAIN ANALYZE 
SELECT * FROM cm.audit_log 
WHERE ts >= now() - interval '1 day'
ORDER BY ts DESC;"
```

## Troubleshooting

### Common Issues
- **Migration Failures**: Check for syntax errors
- **Constraint Violations**: Verify data compatibility
- **Performance Issues**: Check index usage
- **Lock Contention**: Use CONCURRENTLY for large changes

### Recovery Steps
1. Check migration logs
2. Verify database state
3. Test rollback procedures
4. Restore from backup if needed

## Monitoring

### Migration Metrics
- Migration execution time
- Table size changes
- Index usage statistics
- Query performance impact

### Alerts
- Migration failures
- Performance degradation
- Constraint violations
- Lock timeouts

## Documentation

### Schema Documentation
- Table descriptions
- Column definitions
- Index purposes
- Constraint explanations

### Change Log
- Version history
- Migration descriptions
- Rollback procedures
- Performance impact

## Emergency Procedures

### Rollback Process
```bash
# Stop services
make down

# Restore from backup
docker exec -i cm-postgres psql -U cm -d cm < ops/backups/cm_YYYY-MM-DD_HHMMSS.sql

# Restart services
make up

# Verify system
./smoke-test.sh
```

### Emergency Contacts
- Database administrator
- On-call engineer
- Team lead
- Engineering manager
