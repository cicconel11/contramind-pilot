// adyen.ts
import { decideRefund, generateIdempotencyKey, createJWSHash } from "./decide";

export type AdyenRefundRequest = {
  paymentPspReference: string;
  amountMinor: number;
  currency: string;
  customerCountry?: string;
  customerId?: string;
  reason?: string;
};

export type AdyenRefundResponse = {
  success: boolean;
  refund_psp_reference?: string;
  decision: string;
  proof_id: string;
  certificate_jws: string;
  error?: string;
};

export async function refundAdyen(request: AdyenRefundRequest): Promise<AdyenRefundResponse> {
  const { paymentPspReference, amountMinor, currency, customerCountry = "US", customerId, reason } = request;
  const idem = generateIdempotencyKey("adyen", paymentPspReference, amountMinor);

  try {
    // Get decision from Contramind
    const d = await decideRefund({
      amount_minor: amountMinor,
      currency,
      psp: "adyen",
      psp_ref: paymentPspReference,
      country: customerCountry,
      recent: await countRecentRefunds(customerId, 30),
      reason
    }, idem);

    // Store decision in your database
    await saveRefundDecision({
      psp: "adyen",
      psp_ref: paymentPspReference,
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

    // Create Adyen refund
    const refundResponse = await createAdyenRefund({
      paymentPspReference,
      amountMinor,
      currency,
      proofId: d.proof_id,
      idempotencyKey: idem
    });

    if (!refundResponse.success) {
      return {
        success: false,
        decision: "ERROR",
        proof_id: d.proof_id,
        certificate_jws: d.certificate_jws,
        error: refundResponse.error
      };
    }

    // Update database with Adyen refund reference
    await updateRefundDecision(idem, { 
      adyen_refund_reference: refundResponse.pspReference 
    });

    return {
      success: true,
      refund_psp_reference: refundResponse.pspReference,
      decision: d.decision,
      proof_id: d.proof_id,
      certificate_jws: d.certificate_jws
    };

  } catch (error) {
    console.error("Adyen refund error:", error);
    return {
      success: false,
      decision: "ERROR",
      proof_id: "",
      certificate_jws: "",
      error: error instanceof Error ? error.message : "Unknown error"
    };
  }
}

async function createAdyenRefund(params: {
  paymentPspReference: string;
  amountMinor: number;
  currency: string;
  proofId: string;
  idempotencyKey: string;
}): Promise<{ success: boolean; pspReference?: string; error?: string }> {
  const { paymentPspReference, amountMinor, currency, proofId, idempotencyKey } = params;

  const adyenApiKey = process.env.ADYEN_API_KEY;
  const adyenMerchantAccount = process.env.ADYEN_MERCHANT_ACCOUNT;
  const adyenEnvironment = process.env.ADYEN_ENVIRONMENT || "test";

  if (!adyenApiKey || !adyenMerchantAccount) {
    throw new Error("Adyen API key and merchant account are required");
  }

  const baseUrl = adyenEnvironment === "live" 
    ? "https://checkout-live.adyen.com" 
    : "https://checkout-test.adyen.com";

  const refundData = {
    merchantAccount: adyenMerchantAccount,
    amount: {
      value: amountMinor,
      currency: currency
    },
    reference: `cm:${paymentPspReference}:${amountMinor}:${Date.now()}`,
    additionalData: {
      cm_proof_id: proofId,
      cm_decision: "PASS"
    }
  };

  try {
    const response = await fetch(`${baseUrl}/v70/payments/${paymentPspReference}/refunds`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": adyenApiKey,
        "Idempotency-Key": idempotencyKey
      },
      body: JSON.stringify(refundData)
    });

    const result = await response.json();

    if (response.ok) {
      return {
        success: true,
        pspReference: result.pspReference
      };
    } else {
      return {
        success: false,
        error: result.message || `HTTP ${response.status}`
      };
    }

  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Network error"
    };
  }
}

// Express.js endpoint example
export async function createAdyenRefundEndpoint(req: any, res: any) {
  try {
    const { paymentPspReference, amountMinor, currency, customerCountry = "US", customerId, reason } = req.body;

    if (!paymentPspReference || !amountMinor || !currency) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    const result = await refundAdyen({
      paymentPspReference,
      amountMinor,
      currency,
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
    console.error("Adyen refund endpoint error:", error);
    res.status(500).json({ 
      error: "Internal server error",
      message: error instanceof Error ? error.message : "Unknown error"
    });
  }
}

// Adyen webhook handler for refund notifications
export async function handleAdyenRefundWebhook(req: any, res: any) {
  try {
    const { notificationItems } = req.body;

    for (const item of notificationItems) {
      const { NotificationRequestItem } = item;
      const { eventCode, pspReference, originalReference, success } = NotificationRequestItem;

      if (eventCode === "REFUND" && success) {
        // Find the refund decision by original reference and amount
        const refundDecision = await findRefundDecisionByReference(originalReference);
        
        if (refundDecision) {
          // Update with final Adyen reference
          await updateRefundDecision(refundDecision.idempotency_key, {
            adyen_refund_reference: pspReference,
            status: "completed",
            completed_at: new Date().toISOString()
          });

          console.log(`Refund completed: ${pspReference} for decision ${refundDecision.proof_id}`);
        }
      }
    }

    res.status(200).json({ status: "received" });

  } catch (error) {
    console.error("Adyen webhook error:", error);
    res.status(500).json({ error: "Webhook processing failed" });
  }
}

// --- Database helpers (implement these in your app) ---
async function countRecentRefunds(customerId?: string, days: number = 30): Promise<number> {
  // TODO: Implement based on your database
  return 0;
}

async function saveRefundDecision(decision: any): Promise<void> {
  // TODO: Implement based on your database
  console.log("Saving Adyen refund decision:", decision);
}

async function updateRefundDecision(idempotencyKey: string, updates: any): Promise<void> {
  // TODO: Implement based on your database
  console.log("Updating Adyen refund decision:", idempotencyKey, updates);
}

async function findRefundDecisionByReference(originalReference: string): Promise<any> {
  // TODO: Implement based on your database
  // Find by psp_ref field
  return null;
}
