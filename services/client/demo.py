import os, json, time, requests, hashlib
from psycopg_pool import ConnectionPool

PGHOST = os.getenv("PGHOST", "localhost")
PGUSER = os.getenv("PGUSER", "cm")
PGPASSWORD = os.getenv("PGPASSWORD", "cm")
PGDATABASE = os.getenv("PGDATABASE", "cm")
PGPORT = int(os.getenv("PGPORT", "5432"))
ATTESTOR_URL = os.getenv("ATTESTOR_URL", "http://localhost:8082")
WORLDCHECK_URL = os.getenv("WORLDCHECK_URL", "http://localhost:8081")

POOL = ConnectionPool(conninfo=f"host={PGHOST} port={PGPORT} dbname={PGDATABASE} user={PGUSER} password={PGPASSWORD}",
                      min_size=1, max_size=5, timeout=5)

def decide(amount, country, ts, recent):
    with POOL.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT cm.decide_json(%s::numeric, %s::text, %s::timestamptz, %s::int);",
            (amount, country, ts, recent)
        )
        row = cur.fetchone()
        return row[0]

def main():
    # Wait for Postgres
    for i in range(30):
        try:
            with POOL.connection() as conn:
                with conn.cursor() as cur:
                    print("Connected to Postgres")
                    # Try a few decisions
                    cases = [
                        (100.0, "US", "2025-09-16T12:00:00Z", 0),
                        (5000.0, "RU", "2025-09-16T14:00:00Z", 0),
                        (2800.0, "US", "2025-09-14T13:00:00Z", 3),
                    ]
                    for amt, ctry, ts, rec in cases:
                        bundle = decide(amt, ctry, ts, rec)
                        print("\nDecision bundle:", json.dumps(bundle, indent=2))
                        # If NEED_ONE_BIT, call worldcheck and re-evaluate policy client-side (for demo only)
                        if bundle.get("needs_one_bit"):
                            resp = requests.post(f"{WORLDCHECK_URL}/verify", json={"type": "issuer_verify"}).json()
                            print("WorldCheck bit:", resp)
                            # naive: if bit true -> pass, else hold (demo logic)
                            bundle["decision"] = "PASS" if resp["bit"] else "HOLD_HUMAN"
                            bundle["obligations_satisfied"] = (bundle.get("obligations_satisfied") or []) + ["min_info"]
                            bundle["needs_one_bit"] = False

                        # Attest (sign) the proof bundle
                        attest = requests.post(f"{ATTESTOR_URL}/sign", json={"bundle": bundle}).json()
                        print("Attestation:", json.dumps(attest, indent=2))
                        print("kid:", attest.get("kid", "unknown"))
                        
                        # Compute proof_id and insert into ledger
                        canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
                        proof_id = hashlib.sha256(canonical + attest["signature_b64"].encode()).hexdigest()
                        print("proof_id:", proof_id)
                        
                        # Insert into ledger
                        cur.execute("CREATE TABLE IF NOT EXISTS cm.decision_ledger( \
                          id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ DEFAULT now(), proof_id TEXT, \
                          kernel_id TEXT, param_hash TEXT, kid TEXT, bundle JSONB);")
                        cur.execute("INSERT INTO cm.decision_ledger(proof_id,kernel_id,param_hash,kid,bundle) VALUES (%s,%s,%s,%s,%s)",
                                    (proof_id, bundle["kernel_id"], bundle["param_hash"], attest.get("kid", "unknown"), json.dumps(bundle)))
                        conn.commit()

                    return
        except Exception as e:
            print("Waiting for Postgres...", e)
            time.sleep(2)

if __name__ == "__main__":
    main()
