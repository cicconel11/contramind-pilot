import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from psycopg_pool import ConnectionPool
from prometheus_fastapi_instrumentator import Instrumentator

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")

PGHOST=os.getenv("PGHOST","postgres"); PGUSER=os.getenv("PGUSER","cm")
PGPASSWORD=os.getenv("PGPASSWORD","cm"); PGDATABASE=os.getenv("PGDATABASE","cm")
PGPORT=int(os.getenv("PGPORT","5432"))

POOL = ConnectionPool(conninfo=f"host={PGHOST} port={PGPORT} dbname={PGDATABASE} user={PGUSER} password={PGPASSWORD}",
                      min_size=1, max_size=5, timeout=5)

def check(auth: str|None):
    if auth != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

def q(sql, args=()):
    with POOL.connection() as c:
        with c.cursor() as cur:
            cur.execute(sql, args)
            try: rows = cur.fetchall()
            except: rows = None
            c.commit()
            return rows

app = FastAPI(title="Control Plane Lite", version="0.1.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/param/hash")
def param_hash(auth: str|None = Header(None, alias="Authorization")):
    check(auth)
    h = q("SELECT param_hash FROM cm.param_hash_view")[0][0]
    return {"param_hash": h}

@app.get("/params")
def get_params(auth: str|None = Header(None, alias="Authorization")):
    check(auth)
    thresholds = q("SELECT k, v FROM cm.params_thresholds")
    allowlist = q("SELECT country FROM cm.params_allowlist")
    param_hash = q("SELECT param_hash FROM cm.param_hash_view")[0][0]
    return {
        "param_hash": param_hash,
        "thresholds": {k: v for k, v in thresholds},
        "allowlist": [c[0] for c in allowlist]
    }

class ThresholdReq(BaseModel):
    k: str = "amount_max"
    v: float
@app.post("/param/threshold")
def set_threshold(body: ThresholdReq, auth: str|None = Header(None, alias="Authorization")):
    check(auth)
    q("INSERT INTO cm.params_thresholds(k,v) VALUES (%s,%s) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v", (body.k, body.v))
    return param_hash(auth)

class AllowReq(BaseModel):
    country: str
    action: str  # "add" | "remove"
@app.post("/param/allowlist")
def set_allow(body: AllowReq, auth: str|None = Header(None, alias="Authorization")):
    check(auth)
    if body.action == "add":
        q("INSERT INTO cm.params_allowlist(country) VALUES (%s) ON CONFLICT DO NOTHING", (body.country,))
    elif body.action == "remove":
        q("DELETE FROM cm.params_allowlist WHERE country=%s", (body.country,))
    else:
        raise HTTPException(status_code=400, detail="action must be add|remove")
    return param_hash(auth)

@app.get("/healthz")
def healthz(): return {"ok": True}
