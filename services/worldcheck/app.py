import os, random, time
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="WorldCheck", version="0.1.0")
LAT_MAX_MS = int(os.getenv("WC_LATENCY_MAX_MS", "1500"))

class VerifyReq(BaseModel):
    type: str = "issuer_verify"
    tx_id: str | None = None
    force: bool | None = None  # if provided, overrides randomness

class VerifyResp(BaseModel):
    bit: bool
    latency_ms: int

@app.post("/verify", response_model=VerifyResp)
def verify(req: VerifyReq):
    # simulate network/vendor latency
    latency = random.randint(100, LAT_MAX_MS)
    time.sleep(latency / 1000.0)
    if req.force is not None:
        bit = bool(req.force)
    else:
        bit = random.random() > 0.5
    return {"bit": bit, "latency_ms": latency}
