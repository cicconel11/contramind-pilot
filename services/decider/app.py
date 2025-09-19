import os, time, hashlib, base64
import orjson as json
import requests
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from psycopg_pool import ConnectionPool

PGHOST=os.getenv("PGHOST","postgres"); PGUSER=os.getenv("PGUSER","cm")
PGPASSWORD=os.getenv("PGPASSWORD","cm"); PGDATABASE=os.getenv("PGDATABASE","cm")
PGPORT=int(os.getenv("PGPORT","5432"))
ATTESTOR=os.getenv("ATTESTOR_URL","http://attestor:8080")
WORLDCHECK=os.getenv("WORLDCHECK_URL","http://worldcheck:8080")

pool = ConnectionPool(f"host={PGHOST} port={PGPORT} dbname={PGDATABASE} user={PGUSER} password={PGPASSWORD}",
                      min_size=1, max_size=5)

app = FastAPI(title="contramind-decider")

class DecideIn(BaseModel):
    amount: float
    country: str
    ts: datetime
    recent: int = 0
    context_id: str | None = None

class DecideOut(BaseModel):
    decision: str
    obligations: list[str]
    kernel_id: str
    param_hash: str
    kid: str
    signature_b64: str
    proof_id: str
    anchor: dict | None = None
    certificate_jws: str

B64URL = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")

# canonical JSON for proof hashing
CJOPTS = json.OPT_SORT_KEYS | json.OPT_OMIT_MICROSECONDS

@app.get("/healthz")
def health():
    with pool.connection() as cn, cn.cursor() as cur:
        cur.execute("SELECT 1")
        return {"ok": True}

@app.post("/decide", response_model=DecideOut)
def decide(payload: DecideIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    idem_key = idempotency_key or f"auto:{hashlib.sha256(json.dumps(payload.model_dump(), option=CJOPTS)).hexdigest()}"

    # 1) idempotency: return cached response if exists
    with pool.connection() as cn, cn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cm.idempotency (
              id_key text primary key,
              response jsonb not null,
              created_at timestamptz default now()
            );
        """)
        cur.execute("SELECT response FROM cm.idempotency WHERE id_key=%s", (idem_key,))
        row = cur.fetchone()
        if row:
            return row[0]

    # 2) kernel decision
    with pool.connection() as cn, cn.cursor() as cur:
        cur.execute("SELECT cm.decide_json(%s::numeric,%s::text,%s::timestamptz,%s::int)",
                    (payload.amount, payload.country, payload.ts, payload.recent))
        decision_obj = cur.fetchone()[0]

    decision = decision_obj.get("decision")
    obligations = decision_obj.get("obligations", [])
    kernel_id = decision_obj.get("kernel_id", "")
    param_hash = decision_obj.get("param_hash", "")

    # 3) ask one-bit if needed
    if decision == "NEED_ONE_BIT":
        r = requests.post(f"{WORLDCHECK}/verify", json={"type":"issuer_verify"}, timeout=5)
        r.raise_for_status()
        bit = r.json().get("bit")
        if bit:
            decision = "PASS"
        else:
            decision = "HOLD_HUMAN"
        obligations.append("worldcheck_queried")

    # 4) build canonical bundle and sign (legacy /sign for proof_id)
    bundle = {
        "ts": datetime.utcnow().isoformat()+"Z",
        "decision": decision,
        "obligations": obligations,
        "kernel_id": kernel_id,
        "param_hash": param_hash,
        "inputs": {
            "amount": payload.amount,
            "country": payload.country,
            "recent": payload.recent
        }
    }
    canon = json.dumps(bundle, option=CJOPTS)
    digest_hex = hashlib.sha256(canon).hexdigest()

    sig_res = requests.post(f"{ATTESTOR}/sign", json={"bundle": bundle}, timeout=5)
    sig_res.raise_for_status()
    sig_body = sig_res.json()
    kid = sig_body.get("kid")
    signature_b64 = sig_body.get("signature_b64")

    proof_id = hashlib.sha256((canon.decode()+"|"+signature_b64).encode()).hexdigest()

    # 5) Create JWS decision certificate via new /sign_jws
    cert_payload = {
        "sub": "decision",
        "ts": bundle["ts"],
        "decision": decision,
        "kernel_id": kernel_id,
        "param_hash": param_hash,
        "inputs": bundle["inputs"],
        "obligations": obligations,
        "proof_id": proof_id
    }
    jws_res = requests.post(f"{ATTESTOR}/sign_jws", json={"payload": cert_payload}, timeout=5)
    jws_res.raise_for_status()
    certificate_jws = jws_res.json()["jws"]

    out = DecideOut(
        decision=decision,
        obligations=obligations,
        kernel_id=kernel_id,
        param_hash=param_hash,
        kid=kid,
        signature_b64=signature_b64,
        proof_id=proof_id,
        anchor=None,
        certificate_jws=certificate_jws
    ).model_dump()

    # 6) write ledger (including JWS) and idempotency cache
    with pool.connection() as cn, cn.cursor() as cur:
        # ensure new columns exist
        cur.execute("""
          DO $$ BEGIN
            IF NOT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_schema='cm' AND table_name='decision_ledger' AND column_name='certificate_jws') THEN
              ALTER TABLE cm.decision_ledger ADD COLUMN certificate_jws text;
            END IF;
            IF NOT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_schema='cm' AND table_name='decision_ledger' AND column_name='idempotency_key') THEN
              ALTER TABLE cm.decision_ledger ADD COLUMN idempotency_key text;
              CREATE UNIQUE INDEX IF NOT EXISTS decision_ledger_idem_idx ON cm.decision_ledger(idempotency_key);
            END IF;
          END $$;
        """)
        cur.execute(
          """
          INSERT INTO cm.decision_ledger(kernel_id, param_hash, bundle, proof_id, certificate_jws, idempotency_key)
          VALUES (%s,%s,%s::jsonb,%s,%s,%s)
          ON CONFLICT (idempotency_key) DO NOTHING
          """,
          (
            kernel_id,
            param_hash,
            json.dumps(bundle, option=CJOPTS).decode(),
            proof_id,
            certificate_jws,
            idem_key
          )
        )
        cur.execute("INSERT INTO cm.idempotency(id_key, response) VALUES (%s, %s::jsonb) ON CONFLICT (id_key) DO NOTHING",
                    (idem_key, json.dumps(out, option=CJOPTS).decode()))

    return out
