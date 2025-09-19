import os, json, base64, hashlib, time
import orjson
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from nacl import signing, exceptions
from prometheus_fastapi_instrumentator import Instrumentator

# Hold multiple keys; rotate by env
# Format: "kid1:seed1;kid2:seed2"
RAW = os.getenv("ATTESTOR_KEYS", "ed25519:v1:demo-seed-change-me").split(";")
KEYRING = {}
ACTIVE_KID = os.getenv("ATTESTOR_ACTIVE_KID", "ed25519:v1")
for entry in RAW:
    # supports "kid:seed" (legacy) or "alg:kid:seed"
    parts = entry.split(":")
    if len(parts) == 2:
        kid, seed = parts
    else:
        _, kid, seed = parts
    sk = signing.SigningKey(hashlib.sha256(seed.encode()).digest())
    KEYRING[kid] = {"sk": sk, "vk": sk.verify_key}

app = FastAPI(title="Attestor", version="0.2.0-rot")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

class SignReq(BaseModel):
    bundle: dict

class SignResp(BaseModel):
    signature_b64: str
    public_key_b64: str
    digest_hex: str
    kid: str

@app.get("/keys")
def keys():
    return {
        "active": ACTIVE_KID,
        "keys": {kid: base64.b64encode(bytes(v["vk"])).decode() for kid, v in KEYRING.items()}
    }

@app.get("/pubkey")
def pubkey():
    return {"public_key_b64": base64.b64encode(bytes(KEYRING[ACTIVE_KID]["vk"])).decode()}

@app.post("/sign", response_model=SignResp)
def sign(req: SignReq):
    if ACTIVE_KID not in KEYRING:
        raise HTTPException(status_code=500, detail="no active key")
    canonical = json.dumps(req.bundle, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    sk = KEYRING[ACTIVE_KID]["sk"]
    sig = sk.sign(canonical).signature
    return {
        "signature_b64": base64.b64encode(sig).decode(),
        "public_key_b64": base64.b64encode(bytes(KEYRING[ACTIVE_KID]["vk"])).decode(),
        "digest_hex": digest,
        "kid": ACTIVE_KID,
    }

class VerifyReq(BaseModel):
    bundle: dict
    signature_b64: str
    kid: str | None = None

@app.post("/verify")
def verify(req: VerifyReq):
    canonical = json.dumps(req.bundle, sort_keys=True, separators=(",", ":")).encode()
    sig = base64.b64decode(req.signature_b64)
    kid = req.kid or ACTIVE_KID
    if kid not in KEYRING:
        return {"valid": False, "reason": "unknown_kid"}
    try:
        KEYRING[kid]["vk"].verify(canonical, sig)
        return {"valid": True, "kid": kid}
    except exceptions.BadSignatureError:
        return {"valid": False, "kid": kid}

# --- JWS helpers (EdDSA over Ed25519) ---
B64URL = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")

def jws_compact_sign(payload: dict, signing_key: signing.SigningKey, kid: str) -> str:
    header = {"alg": "EdDSA", "kid": kid, "typ": "JWT"}
    protected = B64URL(orjson.dumps(header, option=orjson.OPT_SORT_KEYS))
    pl = B64URL(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS))
    signing_input = protected + b"." + pl
    sig = signing_key.sign(signing_input).signature
    return f"{protected.decode()}.{pl.decode()}.{B64URL(sig).decode()}"

@app.post("/sign_jws")
def sign_jws(body: dict):
    payload = body.get("payload")
    if payload is None:
        raise HTTPException(status_code=400, detail="payload required")
    # use active kid/key from existing key management
    kid = ACTIVE_KID
    sk = KEYRING[kid]["sk"]  # type: signing.SigningKey
    jws = jws_compact_sign(payload, sk, kid)
    return {"kid": kid, "jws": jws}

@app.post("/verify_jws")
def verify_jws(body: dict):
    jws = body.get("jws")
    if not jws or jws.count(".") != 2:
        raise HTTPException(status_code=400, detail="invalid jws")
    h, p, s = jws.split(".")
    header = orjson.loads(base64.urlsafe_b64decode(h + "=="))
    kid = header.get("kid")
    if kid not in KEYRING:
        raise HTTPException(status_code=400, detail="unknown kid")
    vk = KEYRING[kid]["vk"]  # type: signing.VerifyKey
    signing_input = (h + "." + p).encode()
    sig = base64.urlsafe_b64decode(s + "==")
    try:
        vk.verify(signing_input, sig)
        payload = orjson.loads(base64.urlsafe_b64decode(p + "=="))
        return {"valid": True, "kid": kid, "payload": payload}
    except Exception:
        return {"valid": False}
