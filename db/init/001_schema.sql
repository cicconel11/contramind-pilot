-- 001_schema.sql
CREATE SCHEMA IF NOT EXISTS cm;

-- Parameter tables (content-addressed via hash)
CREATE TABLE IF NOT EXISTS cm.params_allowlist (
  country TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS cm.params_thresholds (
  k TEXT PRIMARY KEY,
  v NUMERIC NOT NULL
);

-- Helper view to compute a param hash (simple md5 over canonicalized params)
CREATE OR REPLACE VIEW cm.param_hash_view AS
SELECT
  md5(
    coalesce((SELECT string_agg(country, ',' ORDER BY country) FROM cm.params_allowlist), '')
    || '|' ||
    coalesce((SELECT string_agg(k || '=' || v::text, ',' ORDER BY k) FROM cm.params_thresholds), '')
  ) AS param_hash;
