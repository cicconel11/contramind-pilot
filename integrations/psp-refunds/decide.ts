// decide.ts — call your /decide once per refund intent
import fetch from "node-fetch";

export type DecideIn = {
  amount_minor: number;     // e.g., 2599 = $25.99
  currency: string;         // "USD"
  reason?: string;          // merchant reason
  psp: "stripe"|"adyen"|"braintree"|"shopify";
  psp_ref: string;          // charge/payment/order/txn id
  country?: string;         // customer country
  recent?: number;          // recent refunds count
};

export type DecideOut = {
  decision: "PASS"|"HOLD_HUMAN"|"REJECT"|"NEED_ONE_BIT";
  obligations: string[];
  kernel_id: string;
  param_hash: string;
  kid: string;
  signature_b64: string;
  proof_id: string;
  certificate_jws: string;
  anchor?: { id: string };
};

export async function decideRefund(in_: DecideIn, idemKey?: string): Promise<DecideOut> {
  // Convert to Contramind format
  const decideBody = {
    amount: in_.amount_minor / 100, // Convert to major units
    country: in_.country || "US",
    ts: new Date().toISOString(),
    recent: in_.recent || 0,
    context_id: `refund:${in_.psp}:${in_.psp_ref}`
  };

  const r = await fetch("http://localhost:8084/decide", {
    method: "POST",
    headers: {
      "content-type":"application/json",
      ...(idemKey ? {"Idempotency-Key": idemKey} : {})
    },
    body: JSON.stringify(decideBody)
  });
  
  if (!r.ok) {
    const errorText = await r.text();
    throw new Error(`decide failed: ${r.status} ${errorText}`);
  }
  
  return r.json();
}

// Helper to generate consistent idempotency keys
export function generateIdempotencyKey(psp: string, pspRef: string, amountMinor: number): string {
  return `cm:${psp}:${pspRef}:${amountMinor}`;
}

// Helper to truncate JWS for PSP metadata limits
export function truncateJWS(jws: string, maxLength: number = 4500): string {
  return jws.length > maxLength ? jws.substring(0, maxLength) : jws;
}

// Helper to create JWS hash for storage
export function createJWSHash(jws: string): string {
  const crypto = require('crypto');
  return crypto.createHash('sha256').update(jws).digest('hex');
}
