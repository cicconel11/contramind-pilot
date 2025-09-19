import os, json, base64, time, hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# ----------- Env -----------
DECIDER_URL = os.getenv("DECIDER_URL")  # e.g., http://localhost:8084
KEYS_URL    = os.getenv("ATTESTOR_KEYS_URL", os.getenv("ATTESTOR_URL", "http://localhost:8082") + "/keys")
VERIFY_TLS  = os.getenv("VERIFY_TLS", "1") != "0"  # allow self-signed in dev by setting to 0

# Optional PSP creds
STRIPE_SECRET        = os.getenv("STRIPE_SECRET_KEY")
ADYEN_API_KEY        = os.getenv("ADYEN_API_KEY")
ADYEN_MERCHANT       = os.getenv("ADYEN_MERCHANT")
ADYEN_BASE_URL       = os.getenv("ADYEN_BASE_URL", "https://checkout-test.adyen.com")
BT_MERCHANT_ID       = os.getenv("BT_MERCHANT_ID")
BT_PUBLIC_KEY        = os.getenv("BT_PUBLIC_KEY")
BT_PRIVATE_KEY       = os.getenv("BT_PRIVATE_KEY")
SHOPIFY_SHOP         = os.getenv("SHOPIFY_SHOP")  # myshop
SHOPIFY_TOKEN        = os.getenv("SHOPIFY_TOKEN")
SHOPIFY_API_VERSION  = os.getenv("SHOPIFY_API_VERSION", "2024-07")
DEFAULT_COUNTRY      = os.getenv("DEFAULT_COUNTRY", "US")

if not DECIDER_URL:
    raise RuntimeError("DECIDER_URL is required")

app = FastAPI(title="Refund Orchestrator", version="1.0.0")

# ----------- JWS Verify (EdDSA) -----------
class _KeyCache:
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._exp = 0.0

    async def get(self) -> Dict[str, str]:
        now = time.time()
        if now < self._exp and self._cache:
            return self._cache
        async with httpx.AsyncClient(verify=VERIFY_TLS, timeout=5.0) as client:
            r = await client.get(KEYS_URL)
            r.raise_for_status()
            data = r.json()
        # Accept both {"keys": {kid: base64}} and {"public_key_b64": "..."}
        if isinstance(data, dict) and "keys" in data and isinstance(data["keys"], dict):
            self._cache = {str(k): str(v) for k, v in data["keys"].items()}
        elif isinstance(data, dict) and "public_key_b64" in data:
            self._cache = {"default": str(data["public_key_b64"]) }
        else:
            raise ValueError("Unsupported /keys format: " + json.dumps(data)[:400])
        self._exp = now + 300  # 5 min
        return self._cache

KEYCACHE = _KeyCache()


def _b64url_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))


async def verify_jws_ed25519(jws: str) -> Dict[str, Any]:
    try:
        h_b64, p_b64, s_b64 = jws.split(".")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JWS format")
    header = json.loads(_b64url_dec(h_b64))
    if header.get("alg") not in ("EdDSA", "Ed25519"):
        raise HTTPException(status_code=400, detail="unsupported JWS alg")
    kid = header.get("kid", "default")

    keys = await KEYCACHE.get()
    if kid not in keys:
        raise HTTPException(status_code=400, detail=f"unknown kid: {kid}")
    pubkey_b64 = keys[kid]
    verify_key = VerifyKey(base64.b64decode(pubkey_b64))

    signed_data = (h_b64 + "." + p_b64).encode()
    sig = _b64url_dec(s_b64)

    try:
        verify_key.verify(signed_data, sig)
    except BadSignatureError:
        raise HTTPException(status_code=400, detail="JWS signature verification failed")

    payload = json.loads(_b64url_dec(p_b64))
    return payload

# ----------- /decide Caller -----------
class DecideInput(BaseModel):
    amount_minor: int
    currency: str = Field(..., min_length=3, max_length=3)
    psp: str
    psp_ref: str
    reason: Optional[str] = None
    country: Optional[str] = None
    recent: Optional[int] = 0

async def call_decide(inp: DecideInput, idem: str) -> Dict[str, Any]:
    # translate to kernel inputs (major units + required fields)
    body = {
        "amount": round(inp.amount_minor / 100.0, 2),
        "country": inp.country or DEFAULT_COUNTRY,
        "ts": datetime.now(timezone.utc).isoformat(),
        "recent": int(inp.recent or 0),
        "context_id": f"refund:{inp.psp}:{inp.psp_ref}:{inp.amount_minor}:{inp.currency}",
    }
    async with httpx.AsyncClient(verify=VERIFY_TLS, timeout=7.0) as client:
        r = await client.post(
            f"{DECIDER_URL}/decide" if not DECIDER_URL.endswith("/decide") else DECIDER_URL,
            headers={"Content-Type": "application/json", "Idempotency-Key": idem},
            json=body,
        )
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"decide failed: {r.status_code} {r.text}")
        out = r.json()
    # mandatory: verify certificate locally
    cert = out.get("certificate_jws")
    if not cert:
        raise HTTPException(status_code=502, detail="decide missing certificate_jws")
    payload = await verify_jws_ed25519(cert)  # raises on failure
    # sanity: proof_id match
    if payload.get("proof_id") and out.get("proof_id") and payload["proof_id"] != out["proof_id"]:
        raise HTTPException(status_code=400, detail="certificate payload mismatch")
    return out

# ----------- PSP Adapters -----------

# Stripe
async def stripe_refund(psp_ref: str, amount_minor: int, currency: str, idem: str, proof: Dict[str, Any]) -> Dict[str, Any]:
    if not STRIPE_SECRET:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    import stripe
    stripe.api_key = STRIPE_SECRET
    # Decide whether psp_ref is a charge or payment_intent; Stripe auto-coerces when possible
    kwargs = {"amount": amount_minor, "metadata": {
        "cm_proof_id": proof.get("proof_id", ""),
        "cm_kernel": proof.get("kernel_id", ""),
        "cm_param_hash": proof.get("param_hash", ""),
        "cm_kid": proof.get("kid", ""),
        # Truncate certificate to fit Stripe metadata limits
        "cm_cert_jws": (proof.get("certificate_jws", "")[:4500])
    }}
    # prefer payment_intent, fallback to charge
    try:
        resp = await _stripe_create_refund_async(payment_intent=psp_ref, idem=idemp_key(idem), **kwargs)
    except Exception:
        resp = await _stripe_create_refund_async(charge=psp_ref, idem=idemp_key(idem), **kwargs)
    return {"refund_id": resp.get("id")}

async def _stripe_create_refund_async(**kw):
    # Stripe's SDK is sync; call in threadpool if needed; here we use blocking for brevity
    import stripe
    idem = kw.pop("idem")
    resp = stripe.Refund.create(idempotency_key=idem, **kw)  # type: ignore
    return resp.to_dict() if hasattr(resp, 'to_dict') else resp

# Adyen
async def adyen_refund(psp_ref: str, amount_minor: int, currency: str, idem: str, proof: Dict[str, Any]) -> Dict[str, Any]:
    if not (ADYEN_API_KEY and ADYEN_MERCHANT):
        raise HTTPException(status_code=500, detail="Adyen not configured")
    url = f"{ADYEN_BASE_URL}/v70/payments/{psp_ref}/refunds"
    payload = {
        "merchantAccount": ADYEN_MERCHANT,
        "amount": {"value": amount_minor, "currency": currency},
        "reference": f"cm:{psp_ref}:{amount_minor}",
        "additionalData": {"cm_proof_id": proof.get("proof_id", ""), "cm_kid": proof.get("kid", "")},
    }
    async with httpx.AsyncClient(verify=VERIFY_TLS, timeout=10.0) as client:
        r = await client.post(url, headers={
            "Content-Type": "application/json",
            "X-API-Key": ADYEN_API_KEY,
            "Idempotency-Key": idemp_key(idem)
        }, json=payload)
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Adyen refund failed: {r.status_code} {r.text}")
        return r.json()

# Braintree
async def braintree_refund(psp_ref: str, amount_minor: int, currency: str, idem: str, proof: Dict[str, Any]) -> Dict[str, Any]:
    if not (BT_MERCHANT_ID and BT_PUBLIC_KEY and BT_PRIVATE_KEY):
        raise HTTPException(status_code=500, detail="Braintree not configured")
    import braintree
    gw = braintree.BraintreeGateway(
        environment=braintree.Environment.Sandbox if os.getenv("BT_ENV", "sandbox").lower()=="sandbox" else braintree.Environment.Production,
        merchant_id=BT_MERCHANT_ID, public_key=BT_PUBLIC_KEY, private_key=BT_PRIVATE_KEY)
    # Braintree expects major units string, e.g., "25.99"
    amount_major = f"{amount_minor/100:.2f}"
    res = gw.transaction.refund(psp_ref, amount_major)
    if not res.is_success and not getattr(res, "success", False):
        raise HTTPException(status_code=502, detail=f"Braintree refund failed: {getattr(res, 'message', 'unknown')}")
    txn = res.transaction
    # You may also upsert a custom field on the original sale referencing proof_id
    return {"refund_id": getattr(txn, 'id', None)}

# Shopify (Admin REST)
async def shopify_refund(psp_ref: str, amount_minor: int, currency: str, idem: str, proof: Dict[str, Any]) -> Dict[str, Any]:
    if not (SHOPIFY_SHOP and SHOPIFY_TOKEN):
        raise HTTPException(status_code=500, detail="Shopify not configured")
    order_id = psp_ref
    amount_major = f"{amount_minor/100:.2f}"
    # Create a basic refund (transaction-only). For production, include refund_line_items per your workflow.
    url = f"https://{SHOPIFY_SHOP}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/orders/{order_id}/refunds.json"
    body = {
        "refund": {
            "note": f"cm_proof_id={proof.get('proof_id','')}",
            "currency": currency,
            "shipping": {"full_refund": False},
            "transactions": [{"kind": "refund", "amount": amount_major}]
        }
    }
    async with httpx.AsyncClient(verify=VERIFY_TLS, timeout=10.0) as client:
        r = await client.post(url, headers={
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"
        }, json=body)
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Shopify refund failed: {r.status_code} {r.text}")
        refund_obj = r.json()
        # Attach certificate as metafield (truncated)
        meta_url = f"https://{SHOPIFY_SHOP}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/orders/{order_id}/metafields.json"
        cert_trunc = (proof.get("certificate_jws", "")[:4500]).replace('"','\\"')
        meta_body = {"metafield": {
            "namespace": "contramind", "key": "certificate_jws",
            "type": "multi_line_text_field", "value": cert_trunc
        }}
        try:
            await client.post(meta_url, headers={
                "X-Shopify-Access-Token": SHOPIFY_TOKEN,
                "Content-Type": "application/json"
            }, json=meta_body)
        except Exception:
            pass  # non-fatal
        return refund_obj

# ----------- Utilities -----------
def idemp_key(s: str) -> str:
    # Stripe/Adyen prefer <= 255 ASCII; hash long contexts
    if len(s) <= 200:
        return s
    return "cm:" + hashlib.sha256(s.encode()).hexdigest()[:40]

# ----------- FastAPI Schemas & Routes -----------
class RefundIn(BaseModel):
    amount_minor: int
    currency: str
    psp_ref: str
    reason: Optional[str] = None
    country: Optional[str] = None
    recent: Optional[int] = 0

class RefundOut(BaseModel):
    status: str
    decision: str
    proof_id: Optional[str] = None
    kid: Optional[str] = None
    param_hash: Optional[str] = None
    psp_response: Optional[Dict[str, Any]] = None

@app.post("/refund/stripe", response_model=RefundOut)
async def refund_stripe(in_: RefundIn):
    idem = f"refund:stripe:{in_.psp_ref}:{in_.amount_minor}:{in_.currency}"
    d = DecideInput(amount_minor=in_.amount_minor, currency=in_.currency, psp="stripe", psp_ref=in_.psp_ref, reason=in_.reason, country=in_.country, recent=in_.recent)
    out = await call_decide(d, idem)
    if out["decision"] != "PASS":
        return RefundOut(status=out["decision"], decision=out["decision"], proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"))
    psp_resp = await stripe_refund(in_.psp_ref, in_.amount_minor, in_.currency, idem, out)
    return RefundOut(status="PASS", decision="PASS", proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"), psp_response=psp_resp)

@app.post("/refund/adyen", response_model=RefundOut)
async def refund_adyen(in_: RefundIn):
    idem = f"refund:adyen:{in_.psp_ref}:{in_.amount_minor}:{in_.currency}"
    d = DecideInput(amount_minor=in_.amount_minor, currency=in_.currency, psp="adyen", psp_ref=in_.psp_ref, reason=in_.reason, country=in_.country, recent=in_.recent)
    out = await call_decide(d, idem)
    if out["decision"] != "PASS":
        return RefundOut(status=out["decision"], decision=out["decision"], proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"))
    psp_resp = await adyen_refund(in_.psp_ref, in_.amount_minor, in_.currency, idem, out)
    return RefundOut(status="PASS", decision="PASS", proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"), psp_response=psp_resp)

@app.post("/refund/braintree", response_model=RefundOut)
async def refund_braintree_ep(in_: RefundIn):
    idem = f"refund:braintree:{in_.psp_ref}:{in_.amount_minor}:{in_.currency}"
    d = DecideInput(amount_minor=in_.amount_minor, currency=in_.currency, psp="braintree", psp_ref=in_.psp_ref, reason=in_.reason, country=in_.country, recent=in_.recent)
    out = await call_decide(d, idem)
    if out["decision"] != "PASS":
        return RefundOut(status=out["decision"], decision=out["decision"], proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"))
    psp_resp = await braintree_refund(in_.psp_ref, in_.amount_minor, in_.currency, idem, out)
    return RefundOut(status="PASS", decision="PASS", proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"), psp_response=psp_resp)

@app.post("/refund/shopify", response_model=RefundOut)
async def refund_shopify(in_: RefundIn):
    idem = f"refund:shopify:{in_.psp_ref}:{in_.amount_minor}:{in_.currency}"
    d = DecideInput(amount_minor=in_.amount_minor, currency=in_.currency, psp="shopify", psp_ref=in_.psp_ref, reason=in_.reason, country=in_.country, recent=in_.recent)
    out = await call_decide(d, idem)
    if out["decision"] != "PASS":
        return RefundOut(status=out["decision"], decision=out["decision"], proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"))
    psp_resp = await shopify_refund(in_.psp_ref, in_.amount_minor, in_.currency, idem, out)
    return RefundOut(status="PASS", decision="PASS", proof_id=out.get("proof_id"), kid=out.get("kid"), param_hash=out.get("param_hash"), psp_response=psp_resp)

@app.get("/healthz")
async def healthz():
    return {"ok": True, "decider": DECIDER_URL, "keys": KEYS_URL}
