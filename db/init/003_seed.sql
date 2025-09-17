-- 003_seed.sql
INSERT INTO cm.params_thresholds(k, v) VALUES
  ('amount_max', 2750)
ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v;

INSERT INTO cm.params_allowlist(country) VALUES
  ('US'), ('CA'), ('GB')
ON CONFLICT DO NOTHING;
