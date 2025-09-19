#!/usr/bin/env node
// verify-cert.js - Offline JWS certificate verification tool

import fetch from "node-fetch";
import { jwtVerify, createRemoteJWKSet } from "jose";

const ATTESTOR_URL = process.env.CONTRAMIND_ATTESTOR_URL || "http://localhost:8082";

async function verifyCertificate(jws, keysUrl = `${ATTESTOR_URL}/keys`) {
  try {
    // Parse JWS
    const [headerPart, payloadPart, signaturePart] = jws.split('.');
    
    if (!headerPart || !payloadPart || !signaturePart) {
      throw new Error("Invalid JWS format");
    }
    
    // Decode header
    const header = JSON.parse(Buffer.from(headerPart, 'base64url').toString());
    const kid = header.kid;
    
    if (!kid) {
      throw new Error("Missing kid in JWS header");
    }
    
    // Fetch keys from attestor
    const keysResponse = await fetch(keysUrl);
    if (!keysResponse.ok) {
      throw new Error(`Failed to fetch keys: ${keysResponse.status}`);
    }
    
    const keys = await keysResponse.json();
    const publicKeyB64 = keys.keys[kid];
    
    if (!publicKeyB64) {
      throw new Error(`Unknown key ID: ${kid}`);
    }
    
    // Convert to JWK format for jose library
    const publicKeyBytes = Buffer.from(publicKeyB64, 'base64');
    const jwk = {
      kty: 'OKP',
      crv: 'Ed25519',
      x: Buffer.from(publicKeyBytes).toString('base64url'),
      use: 'sig',
      alg: 'EdDSA',
      kid: kid
    };
    
    // Verify signature
    const { payload, protectedHeader } = await jwtVerify(jws, jwk, {
      algorithms: ["EdDSA"],
    });
    
    return {
      valid: true,
      header: protectedHeader,
      payload: payload,
      kid: kid
    };
    
  } catch (error) {
    return {
      valid: false,
      error: error.message
    };
  }
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const jws = process.argv[2];
  const keysUrl = process.argv[3] || `${ATTESTOR_URL}/keys`;
  
  if (!jws) {
    console.error("Usage: node verify-cert.js <JWS> [keys-url]");
    process.exit(1);
  }
  
  const result = await verifyCertificate(jws, keysUrl);
  
  if (result.valid) {
    console.log("✅ VALID");
    console.log("Header:", JSON.stringify(result.header, null, 2));
    console.log("Payload:", JSON.stringify(result.payload, null, 2));
  } else {
    console.log("❌ INVALID");
    console.log("Error:", result.error);
    process.exit(1);
  }
}

export { verifyCertificate };
