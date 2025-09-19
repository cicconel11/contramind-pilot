// stripe.ts
import Stripe from "stripe";
import { decideRefund, generateIdempotencyKey, truncateJWS, createJWSHash } from "./decide";

const stripe = new Stripe(process.env.STRIPE_SECRET!, {apiVersion:"2024-06-20"});

export type StripeRefundRequest = {
  chargeId?: string;
  paymentIntentId?: string;
  amountMinor: number;
  currency?: string;
  customerCountry?: string;
  customerId?: string;
  reason?: string;
};

export type StripeRefundResponse = {
  success: boolean;
  refund_id?: string;
  decision: string;
  proof_id: string;
  certificate_jws: string;
  error?: string;
};

export async function refundStripe(request: StripeRefundRequest): Promise<StripeRefundResponse> {
  const { chargeId, paymentIntentId, amountMinor, currency = "USD", customerCountry = "US", customerId, reason } = request;
  
  if (!chargeId && !paymentIntentId) {
    throw new Error("Either chargeId or paymentIntentId is required");
  }

  const pspRef = chargeId || paymentIntentId!;
  const idem = generateIdempotencyKey("stripe", pspRef, amountMinor);

  try {
    // Get decision from Contramind
    const d = await decideRefund({
      amount_minor: amountMinor,
      currency,
      psp: "stripe",
      psp_ref: pspRef,
      country: customerCountry,
      recent: await countRecentRefunds(customerId, 30), // last 30 days
      reason
    }, idem);

    // Store decision in your database
    await saveRefundDecision({
      psp: "stripe",
      psp_ref: pspRef,
      amount_minor: amountMinor,
      currency,
      decision: d.decision,
      proof_id: d.proof_id,
      kid: d.kid,
      param_hash: d.param_hash,
      certificate_jws: d.certificate_jws,
      idempotency_key: idem
    });

    if (d.decision !== "PASS") {
      return {
        success: false,
        decision: d.decision,
        proof_id: d.proof_id,
        certificate_jws: d.certificate_jws
      };
    }

    // Create Stripe refund with decision metadata
    const refundParams: Stripe.RefundCreateParams = {
      amount: amountMinor,
      metadata: {
        cm_proof_id: d.proof_id,
        cm_kernel: d.kernel_id,
        cm_param_hash: d.param_hash,
        cm_kid: d.kid,
        cm_cert_hash: createJWSHash(d.certificate_jws),
        cm_cert_jws: truncateJWS(d.certificate_jws, 4500), // Stripe metadata limit
        cm_decision: d.decision,
        cm_obligations: JSON.stringify(d.obligations)
      }
    };

    // Add charge or payment intent
    if (chargeId) {
      refundParams.charge = chargeId;
    } else {
      refundParams.payment_intent = paymentIntentId;
    }

    // Add reason if provided
    if (reason) {
      refundParams.reason = reason as Stripe.RefundCreateParams.Reason;
    }

    const refund = await stripe.refunds.create(refundParams, { 
      idempotencyKey: idem 
    });

    // Update database with refund ID
    await updateRefundDecision(idem, { stripe_refund_id: refund.id });

    return {
      success: true,
      refund_id: refund.id,
      decision: d.decision,
      proof_id: d.proof_id,
      certificate_jws: d.certificate_jws
    };

  } catch (error) {
    console.error("Stripe refund error:", error);
    return {
      success: false,
      decision: "ERROR",
      proof_id: "",
      certificate_jws: "",
      error: error instanceof Error ? error.message : "Unknown error"
    };
  }
}

// Express.js endpoint example
export async function createStripeRefundEndpoint(req: any, res: any) {
  try {
    const { chargeId, paymentIntentId, amountCents, customerCountry = "US", customerId, reason } = req.body;

    if (!amountCents || (!chargeId && !paymentIntentId)) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    const result = await refundStripe({
      chargeId,
      paymentIntentId,
      amountMinor: amountCents,
      customerCountry,
      customerId,
      reason
    });

    if (result.success) {
      res.json(result);
    } else {
      res.status(202).json(result); // 202 for HOLD_HUMAN/REJECT
    }

  } catch (error) {
    console.error("Refund endpoint error:", error);
    res.status(500).json({ 
      error: "Internal server error",
      message: error instanceof Error ? error.message : "Unknown error"
    });
  }
}

// --- Database helpers (implement these in your app) ---
async function countRecentRefunds(customerId?: string, days: number = 30): Promise<number> {
  // TODO: Implement based on your database
  // Example: SELECT COUNT(*) FROM refunds WHERE customer_id = ? AND created_at > NOW() - INTERVAL ? DAY
  return 0;
}

async function saveRefundDecision(decision: any): Promise<void> {
  // TODO: Implement based on your database
  // Example: INSERT INTO refund_decisions (psp, psp_ref, amount_minor, decision, proof_id, certificate_jws, ...)
  console.log("Saving refund decision:", decision);
}

async function updateRefundDecision(idempotencyKey: string, updates: any): Promise<void> {
  // TODO: Implement based on your database
  // Example: UPDATE refund_decisions SET stripe_refund_id = ? WHERE idempotency_key = ?
  console.log("Updating refund decision:", idempotencyKey, updates);
}
