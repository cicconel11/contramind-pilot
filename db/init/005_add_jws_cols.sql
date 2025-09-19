DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='cm' AND table_name='decision_ledger' AND column_name='certificate_jws'
  ) THEN
    ALTER TABLE cm.decision_ledger ADD COLUMN certificate_jws text;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='cm' AND table_name='decision_ledger' AND column_name='idempotency_key'
  ) THEN
    ALTER TABLE cm.decision_ledger ADD COLUMN idempotency_key text;
    CREATE UNIQUE INDEX IF NOT EXISTS decision_ledger_idem_idx ON cm.decision_ledger(idempotency_key);
  END IF;
END $$;
