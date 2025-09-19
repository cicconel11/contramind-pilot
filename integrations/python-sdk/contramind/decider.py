import requests
import base64
import json
import uuid
from typing import Dict, Any, Optional
from nacl.signing import VerifyKey
from pydantic import BaseModel


class DecisionInputs(BaseModel):
    amount: float
    country: str
    ts: str
    recent: int = 0
    context_id: Optional[str] = None


class DecisionResult(BaseModel):
    decision: str
    obligations: list[str]
    kernel_id: str
    param_hash: str
    kid: str
    signature_b64: str
    proof_id: str
    anchor: Optional[Dict[str, Any]] = None
    certificate_jws: str
    verified: bool = False
    verification_error: Optional[str] = None
    certificate_payload: Optional[Dict[str, Any]] = None


def b64url_dec(s: str) -> bytes:
    """Decode base64url string"""
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def verify_jws(jws: str, attestor_url: str = "http://localhost:8082") -> Dict[str, Any]:
    """
    Verify a JWS certificate offline
    
    Args:
        jws: JWS certificate string
        attestor_url: Attestor service URL
        
    Returns:
        Verified payload
        
    Raises:
        Exception: If verification fails
    """
    h, p, s = jws.split(".")
    header = json.loads(b64url_dec(h).decode())
    kid = header["kid"]
    
    # Fetch keys from attestor
    keys_response = requests.get(f"{attestor_url}/keys")
    keys_response.raise_for_status()
    keys = keys_response.json()["keys"]
    
    # Get the verification key
    key_b64 = keys[kid]
    vk = VerifyKey(base64.b64decode(key_b64))
    
    # Verify signature
    vk.verify((h + "." + p).encode(), b64url_dec(s))
    
    # Return payload
    return json.loads(b64url_dec(p).decode())


class ContramindDecider:
    """
    Contramind Decision API SDK with JWS verification
    """
    
    def __init__(self, decider_url: str = "http://localhost:8084", 
                 attestor_url: str = "http://localhost:8082"):
        self.decider_url = decider_url
        self.attestor_url = attestor_url
    
    def decide(self, inputs: Dict[str, Any], idempotency_key: Optional[str] = None) -> DecisionResult:
        """
        Make a decision with automatic JWS verification
        
        Args:
            inputs: Decision inputs
            idempotency_key: Optional idempotency key
            
        Returns:
            DecisionResult with verification status
        """
        # Validate inputs
        validated_inputs = DecisionInputs(**inputs)
        
        # Generate idempotency key if not provided
        idem = idempotency_key or str(uuid.uuid4())
        
        # Call the decision API
        response = requests.post(
            f"{self.decider_url}/decide",
            json=validated_inputs.model_dump(),
            headers={"Idempotency-Key": idem},
            timeout=30
        )
        response.raise_for_status()
        
        result_data = response.json()
        
        # Verify JWS certificate
        try:
            payload = verify_jws(result_data["certificate_jws"], self.attestor_url)
            result_data["verified"] = True
            result_data["certificate_payload"] = payload
            result_data["verification_error"] = None
        except Exception as e:
            result_data["verified"] = False
            result_data["certificate_payload"] = None
            result_data["verification_error"] = str(e)
        
        return DecisionResult(**result_data)
    
    def verify_certificate(self, jws: str) -> Dict[str, Any]:
        """
        Verify a JWS certificate offline
        
        Args:
            jws: JWS certificate string
            
        Returns:
            Verified payload
        """
        return verify_jws(jws, self.attestor_url)
    
    def get_keys(self) -> Dict[str, Any]:
        """
        Get available attestor keys
        
        Returns:
            Keys information
        """
        response = requests.get(f"{self.attestor_url}/keys")
        response.raise_for_status()
        return response.json()


def stripe_refund_extractor(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract decision inputs from Stripe refund webhook data
    
    Args:
        request_data: Stripe webhook data
        
    Returns:
        Decision inputs
    """
    amount = request_data.get("amount", 0)
    customer = request_data.get("customer", "")
    metadata = request_data.get("metadata", {})
    
    return {
        "amount": amount / 100,  # Convert from cents
        "country": metadata.get("country", "US"),
        "ts": request_data.get("created", ""),
        "recent": int(metadata.get("recent_transactions", "0")),
        "context_id": f"stripe_refund:{customer}"
    }


def stripe_charge_extractor(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract decision inputs from Stripe charge data
    
    Args:
        request_data: Stripe charge data
        
    Returns:
        Decision inputs
    """
    amount = request_data.get("amount", 0)
    customer = request_data.get("customer", "")
    metadata = request_data.get("metadata", {})
    
    return {
        "amount": amount / 100,  # Convert from cents
        "country": metadata.get("country", "US"),
        "ts": request_data.get("created", ""),
        "recent": int(metadata.get("recent_transactions", "0")),
        "context_id": f"stripe_charge:{customer}"
    }
