-- 002_kernel.sql
-- Minimal "kernel" as a PL/pgSQL function. It returns a JSON bundle with decision + obligations + hashes.
-- This simulates a synthesized, proven kernel. For the pilot, it's hand-authored and tiny.
CREATE OR REPLACE FUNCTION cm.decide_json(
  p_amount NUMERIC,
  p_country TEXT,
  p_ts TIMESTAMPTZ,
  p_recent_disputes INT
) RETURNS JSONB LANGUAGE plpgsql AS
$$
DECLARE
  weekend BOOL := EXTRACT(ISODOW FROM p_ts) IN (6,7);
  amount_max NUMERIC;
  allowlist_hit BOOL;
  param_hash_val TEXT;
  kernel_id TEXT := 'K_demo_v1_2750_allowlist';  -- in a real system this is a code hash
  decision TEXT;
  obligations TEXT[] := ARRAY[]::TEXT[];
  needs_one_bit BOOL := FALSE;
BEGIN
  SELECT v INTO amount_max FROM cm.params_thresholds WHERE k='amount_max';
  IF amount_max IS NULL THEN
    RAISE EXCEPTION 'amount_max not configured';
  END IF;

  SELECT EXISTS(SELECT 1 FROM cm.params_allowlist WHERE country = p_country) INTO allowlist_hit;
  SELECT param_hash FROM cm.param_hash_view INTO param_hash_val;

  -- Guardrails (cheap checks first)
  IF allowlist_hit AND p_amount <= amount_max AND NOT weekend THEN
    decision := 'PASS';
    obligations := array_append(obligations, 'privacy_ok');
  ELSIF (p_amount > amount_max) AND (NOT allowlist_hit) AND (p_recent_disputes < 2) THEN
    decision := 'HOLD_HUMAN';
    obligations := array_append(obligations, 'budget_ok');
  ELSE
    decision := 'NEED_ONE_BIT';
    needs_one_bit := TRUE;
  END IF;

  RETURN jsonb_build_object(
    'decision', decision,
    'obligations_satisfied', obligations,
    'kernel_id', kernel_id,
    'param_hash', param_hash_val,
    'needs_one_bit', needs_one_bit
  );
END;
$$;
