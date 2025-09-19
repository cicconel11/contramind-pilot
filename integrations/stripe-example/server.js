import express from "express";
import Stripe from "stripe";
import { createRemoteJWKSet, jwtVerify } from "jose";
import { request } from "undici";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(express.json());

// Initialize Stripe
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

// Initialize Contramind
const DECIDER_URL = process.env.CONTRAMIND_DECIDER_URL || "http://localhost:8084";
const ATTESTOR_URL = process.env.CONTRAMIND_ATTESTOR_URL || "http://localhost:8082";
const JWKS = createRemoteJWKSet(new URL(`${ATTESTOR_URL}/keys`));

/**
 * Make a decision with Contramind and verify the certificate
 */
async function makeDecision(inputs, idempotencyKey) {
  const response = await request(`${DECIDER_URL}/decide`, {
    method: "POST",
    headers: { 
      "content-type": "application/json", 
      "Idempotency-Key": idempotencyKey 
    },
    body: JSON.stringify(inputs),
  });

  if (response.statusCode !== 200) {
    throw new Error(`Decision API error: ${response.statusCode}`);
  }

  const result = await response.body.json();

  // Verify JWS certificate
  try {
    const { payload, protectedHeader } = await jwtVerify(
      result.certificate_jws, 
      JWKS, 
      { algorithms: ["EdDSA"] }
    );
    
    result.verified = true;
    result.certificate_payload = payload;
  } catch (error) {
    result.verified = false;
    result.verification_error = error.message;
  }

  return result;
}

/**
 * Extract decision inputs from Stripe refund data
 */
function extractRefundInputs(refundData) {
  return {
    amount: refundData.amount / 100, // Convert from cents
    country: refundData.metadata?.country || "US",
    ts: new Date(refundData.created * 1000).toISOString(),
    recent: parseInt(refundData.metadata?.recent_transactions || "0"),
    context_id: `stripe_refund:${refundData.customer}`
  };
}

/**
 * Extract decision inputs from Stripe charge data
 */
function extractChargeInputs(chargeData) {
  return {
    amount: chargeData.amount / 100, // Convert from cents
    country: chargeData.metadata?.country || "US",
    ts: new Date(chargeData.created * 1000).toISOString(),
    recent: parseInt(chargeData.metadata?.recent_transactions || "0"),
    context_id: `stripe_charge:${chargeData.customer}`
  };
}

/**
 * Process refund with Contramind decision
 */
app.post("/refund", async (req, res) => {
  try {
    const { charge_id, amount, reason } = req.body;
    
    // Get the original charge
    const charge = await stripe.charges.retrieve(charge_id);
    
    // Extract decision inputs
    const inputs = extractRefundInputs({
      amount: amount || charge.amount,
      customer: charge.customer,
      created: charge.created,
      metadata: charge.metadata
    });
    
    // Make decision
    const idempotencyKey = `refund-${charge_id}-${Date.now()}`;
    const decision = await makeDecision(inputs, idempotencyKey);
    
    // Log decision
    console.log("Refund decision:", {
      charge_id,
      decision: decision.decision,
      verified: decision.verified,
      proof_id: decision.proof_id
    });
    
    if (!decision.verified) {
      return res.status(500).json({
        error: "Certificate verification failed",
        verification_error: decision.verification_error
      });
    }
    
    // Process refund based on decision
    if (decision.decision === "PASS") {
      // Auto-approve refund
      const refund = await stripe.refunds.create({
        charge: charge_id,
        amount: amount,
        reason: reason || "requested_by_customer",
        metadata: {
          contramind_decision: decision.decision,
          contramind_proof_id: decision.proof_id,
          contramind_certificate: decision.certificate_jws,
          contramind_param_hash: decision.param_hash,
          contramind_obligations: JSON.stringify(decision.obligations)
        }
      });
      
      res.json({
        success: true,
        refund_id: refund.id,
        decision: decision.decision,
        proof_id: decision.proof_id,
        certificate_jws: decision.certificate_jws,
        message: "Refund auto-approved"
      });
      
    } else if (decision.decision === "HOLD_HUMAN") {
      // Create refund request for manual review
      const refundRequest = await stripe.refunds.create({
        charge: charge_id,
        amount: amount,
        reason: reason || "requested_by_customer",
        metadata: {
          contramind_decision: decision.decision,
          contramind_proof_id: decision.proof_id,
          contramind_certificate: decision.certificate_jws,
          contramind_param_hash: decision.param_hash,
          contramind_obligations: JSON.stringify(decision.obligations),
          manual_review_required: "true"
        }
      });
      
      res.json({
        success: true,
        refund_id: refundRequest.id,
        decision: decision.decision,
        proof_id: decision.proof_id,
        certificate_jws: decision.certificate_jws,
        message: "Refund created, manual review required"
      });
      
    } else {
      // Reject refund
      res.status(403).json({
        success: false,
        decision: decision.decision,
        proof_id: decision.proof_id,
        certificate_jws: decision.certificate_jws,
        message: "Refund rejected by policy"
      });
    }
    
  } catch (error) {
    console.error("Refund processing error:", error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Process charge with Contramind decision
 */
app.post("/charge", async (req, res) => {
  try {
    const { amount, currency, customer, metadata } = req.body;
    
    // Extract decision inputs
    const inputs = extractChargeInputs({
      amount,
      customer,
      created: Math.floor(Date.now() / 1000),
      metadata
    });
    
    // Make decision
    const idempotencyKey = `charge-${customer}-${Date.now()}`;
    const decision = await makeDecision(inputs, idempotencyKey);
    
    // Log decision
    console.log("Charge decision:", {
      customer,
      amount,
      decision: decision.decision,
      verified: decision.verified,
      proof_id: decision.proof_id
    });
    
    if (!decision.verified) {
      return res.status(500).json({
        error: "Certificate verification failed",
        verification_error: decision.verification_error
      });
    }
    
    // Process charge based on decision
    if (decision.decision === "PASS") {
      // Create charge
      const charge = await stripe.charges.create({
        amount,
        currency,
        customer,
        metadata: {
          ...metadata,
          contramind_decision: decision.decision,
          contramind_proof_id: decision.proof_id,
          contramind_certificate: decision.certificate_jws,
          contramind_param_hash: decision.param_hash,
          contramind_obligations: JSON.stringify(decision.obligations)
        }
      });
      
      res.json({
        success: true,
        charge_id: charge.id,
        decision: decision.decision,
        proof_id: decision.proof_id,
        certificate_jws: decision.certificate_jws,
        message: "Charge approved"
      });
      
    } else {
      // Reject charge
      res.status(403).json({
        success: false,
        decision: decision.decision,
        proof_id: decision.proof_id,
        certificate_jws: decision.certificate_jws,
        message: "Charge rejected by policy"
      });
    }
    
  } catch (error) {
    console.error("Charge processing error:", error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Verify a decision certificate
 */
app.post("/verify", async (req, res) => {
  try {
    const { certificate_jws } = req.body;
    
    const { payload, protectedHeader } = await jwtVerify(certificate_jws, JWKS, {
      algorithms: ["EdDSA"],
    });
    
    res.json({
      valid: true,
      payload,
      header: protectedHeader
    });
    
  } catch (error) {
    res.status(400).json({
      valid: false,
      error: error.message
    });
  }
});

/**
 * Health check
 */
app.get("/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Stripe-Contramind integration running on port ${PORT}`);
  console.log(`📋 Endpoints:`);
  console.log(`   POST /refund - Process refund with decision`);
  console.log(`   POST /charge - Process charge with decision`);
  console.log(`   POST /verify - Verify decision certificate`);
  console.log(`   GET  /health - Health check`);
});
