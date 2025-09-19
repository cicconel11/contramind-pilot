#!/usr/bin/env python3
# verify-cert.py - Offline JWS certificate verification tool

import sys
import base64
import json
import requests
from nacl.signing import VerifyKey

def b64url_dec(s: str) -> bytes:
    """Decode base64url string"""
    pad = '=' * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)

def verify_certificate(jws: str, keys_url: str = "http://localhost:8082/keys") -> dict:
    """
    Verify a JWS certificate offline
    
    Args:
        jws: JWS certificate string
        keys_url: URL to fetch public keys
        
    Returns:
        Verification result with payload if valid
    """
    try:
        # Parse JWS
        h, p, s = jws.split('.')
        
        # Decode header
        header = json.loads(b64url_dec(h).decode())
        kid = header.get('kid')
        
        if not kid:
            raise ValueError("Missing kid in JWS header")
        
        # Fetch keys from attestor
        keys_response = requests.get(keys_url)
        keys_response.raise_for_status()
        keys = keys_response.json()
        
        # Get the public key
        key_b64 = keys['keys'].get(kid)
        if not key_b64:
            raise ValueError(f"Unknown key ID: {kid}")
        
        # Create verification key
        vk = VerifyKey(base64.b64decode(key_b64))
        
        # Verify signature
        vk.verify((h + '.' + p).encode(), b64url_dec(s))
        
        # Decode payload
        payload = json.loads(b64url_dec(p).decode())
        
        return {
            'valid': True,
            'header': header,
            'payload': payload,
            'kid': kid
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }

def main():
    if len(sys.argv) < 2:
        print("Usage: python verify-cert.py <JWS> [keys-url]")
        sys.exit(1)
    
    jws = sys.argv[1]
    keys_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8082/keys"
    
    result = verify_certificate(jws, keys_url)
    
    if result['valid']:
        print("✅ VALID")
        print("Header:", json.dumps(result['header'], indent=2))
        print("Payload:", json.dumps(result['payload'], indent=2))
    else:
        print("❌ INVALID")
        print("Error:", result['error'])
        sys.exit(1)

if __name__ == "__main__":
    main()
