import os, json, base64, hashlib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from nacl import signing, exceptions

SEED = os.getenv("ATTESTOR_SEED", "demo-seed-change-me").encode()
seed32 = hashlib.sha256(SEED).digest()
sk = signing.SigningKey(seed32)
vk = sk.verify_key

app = FastAPI(title="Attestor", version="0.1.0")

class SignReq(BaseModel):
    bundle: dict

class SignResp(BaseModel):
    signature_b64: str
    public_key_b64: str
    digest_hex: str

@app.get("/pubkey")
def pubkey():
    return {"public_key_b64": base64.b64encode(bytes(vk)).decode()}

@app.post("/sign", response_model=SignResp)
def sign(req: SignReq):
    try:
        # Canonicalize bundle deterministically
        canonical = json.dumps(req.bundle, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        sig = sk.sign(canonical).signature
        return {
            "signature_b64": base64.b64encode(sig).decode(),
            "public_key_b64": base64.b64encode(bytes(vk)).decode(),
            "digest_hex": digest,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class VerifyReq(BaseModel):
    bundle: dict
    signature_b64: str

@app.post("/verify")
def verify(req: VerifyReq):
    canonical = json.dumps(req.bundle, sort_keys=True, separators=(",", ":")).encode()
    sig = base64.b64decode(req.signature_b64)
    try:
        vk.verify(canonical, sig)
        return {"valid": True}
    except exceptions.BadSignatureError:
        return {"valid": False}
