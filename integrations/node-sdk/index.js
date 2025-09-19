import { createRemoteJWKSet, jwtVerify } from "jose";
import { request } from "undici";
import { randomUUID } from "crypto";

/**
 * Contramind Decision API SDK
 * Provides decision making with JWS certificate verification
 */
export class ContramindDecider {
  constructor(options = {}) {
    this.deciderUrl = options.deciderUrl || process.env.CONTRAMIND_DECIDER_URL || "http://localhost:8084";
    this.attestorUrl = options.attestorUrl || process.env.CONTRAMIND_ATTESTOR_URL || "http://localhost:8082";
    // Note: We'll fetch keys manually since the attestor doesn't return JWKS format
    this.keys = null;
  }

  /**
   * Make a decision with automatic JWS verification
   * @param {Object} inputs - Decision inputs
   * @param {number} inputs.amount - Transaction amount
   * @param {string} inputs.country - Country code
   * @param {string} inputs.ts - ISO timestamp
   * @param {number} [inputs.recent=0] - Recent transaction count
   * @param {string} [inputs.context_id] - Context identifier
   * @param {string} [idempotencyKey] - Idempotency key (auto-generated if not provided)
   * @returns {Promise<DecisionResult>}
   */
  async decide(inputs, idempotencyKey = null) {
    const idem = idempotencyKey || randomUUID();
    
    // Call the decision API
    const response = await request(`${this.deciderUrl}/decide`, {
      method: "POST",
      headers: { 
        "content-type": "application/json", 
        "Idempotency-Key": idem 
      },
      body: JSON.stringify(inputs),
    });

    if (response.statusCode !== 200) {
      throw new Error(`Decision API error: ${response.statusCode}`);
    }

    const result = await response.body.json();

    // Verify JWS certificate
    try {
      const { payload, protectedHeader } = await this.verifyCertificate(result.certificate_jws);
      result.verified = true;
      result.certificate_payload = payload;
      result.certificate_header = protectedHeader;
    } catch (error) {
      result.verified = false;
      result.verification_error = error.message;
    }

    return result;
  }

  /**
   * Verify a JWS certificate offline
   * @param {string} jws - JWS certificate
   * @returns {Promise<Object>} Verified payload
   */
  async verifyCertificate(jws) {
    // Parse JWS
    const [headerPart, payloadPart, signaturePart] = jws.split('.');
    
    // Decode header
    const header = JSON.parse(Buffer.from(headerPart, 'base64url').toString());
    const kid = header.kid;
    
    // Get keys if not cached
    if (!this.keys) {
      const keysResponse = await request(`${this.attestorUrl}/keys`);
      this.keys = await keysResponse.body.json();
    }
    
    // Get the public key
    const publicKeyB64 = this.keys.keys[kid];
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
    
    return { payload, protectedHeader };
  }

  /**
   * Get available attestor keys
   * @returns {Promise<Object>} Keys information
   */
  async getKeys() {
    const response = await request(`${this.attestorUrl}/keys`);
    return await response.body.json();
  }
}

/**
 * Express middleware for automatic decision making
 * @param {ContramindDecider} decider - Decider instance
 * @param {Function} inputExtractor - Function to extract inputs from request
 * @returns {Function} Express middleware
 */
export function decideMiddleware(decider, inputExtractor) {
  return async (req, res, next) => {
    try {
      const inputs = inputExtractor(req);
      const idem = req.headers["idempotency-key"] || randomUUID();
      
      const result = await decider.decide(inputs, idem);
      
      // Attach decision to request
      req.decision = result.decision;
      req.decisionCert = result.certificate_jws;
      req.paramHash = result.param_hash;
      req.proofId = result.proof_id;
      req.obligations = result.obligations;
      req.verified = result.verified;
      
      next();
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  };
}

/**
 * Stripe-specific input extractor for refunds
 * @param {Object} req - Express request
 * @returns {Object} Decision inputs
 */
export function stripeRefundExtractor(req) {
  const { amount, currency, customer, metadata } = req.body;
  
  return {
    amount: amount / 100, // Convert from cents
    country: metadata?.country || "US",
    ts: new Date().toISOString(),
    recent: parseInt(metadata?.recent_transactions || "0"),
    context_id: `stripe_refund:${customer}`
  };
}

/**
 * Stripe-specific input extractor for charges
 * @param {Object} req - Express request
 * @returns {Object} Decision inputs
 */
export function stripeChargeExtractor(req) {
  const { amount, currency, customer, metadata } = req.body;
  
  return {
    amount: amount / 100, // Convert from cents
    country: metadata?.country || "US", 
    ts: new Date().toISOString(),
    recent: parseInt(metadata?.recent_transactions || "0"),
    context_id: `stripe_charge:${customer}`
  };
}

export default ContramindDecider;
