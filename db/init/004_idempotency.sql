CREATE TABLE IF NOT EXISTS cm.idempotency (
  id_key text PRIMARY KEY,
  response jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);
