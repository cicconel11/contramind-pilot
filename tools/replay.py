import os, json, base64, hashlib, psycopg, requests, sys

PGHOST=os.getenv("PGHOST","localhost"); PGPORT=int(os.getenv("PGPORT","5433")) # host port for convenience
with psycopg.connect(host=PGHOST, port=PGPORT, user="cm", password="cm", dbname="cm") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, bundle FROM cm.decision_ledger ORDER BY id")
        rows = cur.fetchall()
        bad = 0
        for (id_, bundle) in rows:
            # Verify digest deterministically
            canonical=json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
            digest=hashlib.sha256(canonical).hexdigest()
            # Re-evaluate decision using current kernel
            cur.execute("SELECT cm.decide_json(%s::numeric,%s::text,%s::timestamptz,%s::int)",
                        (bundle.get("amount", 100), bundle.get("country","US"),
                         bundle.get("ts","2025-09-16T12:00:00Z"), bundle.get("recent",0)))
            now=cur.fetchone()[0]["decision"]
            recorded=bundle["decision"]
            if now != recorded:
                bad += 1
                print(f"[DRIFT] id={id_} recorded={recorded} now={now} digest={digest}")
        print(f"Checked {len(rows)} decisions, drift={bad}")
