// braintree.ts
import braintree from "braintree";
import { decideRefund, generateIdempotencyKey, createJWSHash } from "./decide";

// Initialize Braintree gateway
const gateway = new braintree.BraintreeGateway({
  environment: process.env.BRAINTREE_ENVIRONMENT === "production" 
    ? braintree.Environment.Production 
    : braintree.Environment.Sandbox,
  merchantId: process.env.BRAINTREE_MERCHANT_ID!,
  publicKey: process.env.BRAINTREE_PUBLIC_KEY!,
  privateKey: process.env.BRAINTREE_PRIVATE_KEY!,
});

export type BraintreeRefundRequest = {
  originalTransactionId: string;
  amountMinor: number;
  currency?: string;
  customerCountry?: string;
  customerId?: string;
  reason?: string;
};

export type BraintreeRefundResponse = {
  success: boolean;
  refund_transaction_id?: string;
  decision: string;
  proof_id: string;
  certificate_jws: string;
  error?: string;
};

export async function refundBraintree(request: BraintreeRefundRequest): Promise<BraintreeRefundResponse> {
  const { originalTransactionId, amountMinor, currency = "USD", customerCountry = "US", customerId, reason } = request;
  const idem = generateIdempotencyKey("braintree", originalTransactionId, amountMinor);

  try {
    // Get decision from Contramind
    const d = await decideRefund({
      amount_minor: amountMinor,
      currency,
      psp: "braintree",
      psp_ref: originalTransactionId,
      country: customerCountry,
      recent: await countRecentRefunds(customerId, 30),
      reason
    }, idem);

    // Store decision in your database
    await saveRefundDecision({
      psp: "braintree",
      psp_ref: originalTransactionId,
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

    // Create Braintree refund
    const refundResult = await createBraintreeRefund({
      originalTransactionId,
      amountMinor,
      proofId: d.proof_id,
      certificateJws: d.certificate_jws
    });

    if (!refundResult.success) {
      return {
        success: false,
        decision: "ERROR",
        proof_id: d.proof_id,
        certificate_jws: d.certificate_jws,
        error: refundResult.error
      };
    }

    // Update database with Braintree refund transaction ID
    await updateRefundDecision(idem, { 
      braintree_refund_id: refundResult.transactionId 
    });

    return {
      success: true,
      refund_transaction_id: refundResult.transactionId,
      decision: d.decision,
      proof_id: d.proof_id,
      certificate_jws: d.certificate_jws
    };

  } catch (error) {
    console.error("Braintree refund error:", error);
    return {
      success: false,
      decision: "ERROR",
      proof_id: "",
      certificate_jws: "",
      error: error instanceof Error ? error.message : "Unknown error"
    };
  }
}

async function createBraintreeRefund(params: {
  originalTransactionId: string;
  amountMinor: number;
  proofId: string;
  certificateJws: string;
}): Promise<{ success: boolean; transactionId?: string; error?: string }> {
  const { originalTransactionId, amountMinor, proofId, certificateJws } = params;

  try {
    // Convert amount to string format (e.g., "25.99")
    const amountString = (amountMinor / 100).toFixed(2);

    // Create refund transaction
    const result = await gateway.transaction.refund(originalTransactionId, amountString);

    if (result.success && result.transaction) {
      // Store decision certificate in custom fields (if supported)
      try {
        await updateBraintreeTransactionCustomFields(result.transaction.id, {
          cm_proof_id: proofId,
          cm_cert_hash: createJWSHash(certificateJws),
          cm_decision: "PASS"
        });
      } catch (fieldError) {
        console.warn("Failed to update custom fields:", fieldError);
        // Continue - this is not critical
      }

      return {
        success: true,
        transactionId: result.transaction.id
      };
    } else {
      return {
        success: false,
        error: result.message || "Refund failed"
      };
    }

  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Network error"
    };
  }
}

async function updateBraintreeTransactionCustomFields(transactionId: string, fields: Record<string, string>): Promise<void> {
  // Note: Braintree doesn't have a direct API to update transaction custom fields after creation
  // You would need to store this information in your own database
  // This is a placeholder for where you might store the decision metadata
  console.log(`Storing decision metadata for Braintree transaction ${transactionId}:`, fields);
  
  // TODO: Implement your own storage mechanism
  // Example: Store in your database with transaction_id as key
  await storeBraintreeDecisionMetadata(transactionId, fields);
}

// Express.js endpoint example
export async function createBraintreeRefundEndpoint(req: any, res: any) {
  try {
    const { originalTransactionId, amountCents, currency = "USD", customerCountry = "US", customerId, reason } = req.body;

    if (!originalTransactionId || !amountCents) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    const result = await refundBraintree({
      originalTransactionId,
      amountMinor: amountCents,
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
    console.error("Braintree refund endpoint error:", error);
    res.status(500).json({ 
      error: "Internal server error",
      message: error instanceof Error ? error.message : "Unknown error"
    });
  }
}

// Braintree webhook handler (if using webhooks)
export async function handleBraintreeWebhook(req: any, res: any) {
  try {
    const { bt_signature, bt_payload } = req.body;

    // Verify webhook signature
    const webhookNotification = gateway.webhookNotification.parse(bt_signature, bt_payload);

    if (webhookNotification.kind === "transaction_refunded") {
      const transaction = webhookNotification.transaction;
      
      // Find the refund decision by original transaction ID
      const refundDecision = await findRefundDecisionByReference(transaction.refundedTransactionId);
      
      if (refundDecision) {
        // Update with final Braintree refund transaction ID
        await updateRefundDecision(refundDecision.idempotency_key, {
          braintree_refund_id: transaction.id,
          status: "completed",
          completed_at: new Date().toISOString()
        });

        console.log(`Braintree refund completed: ${transaction.id} for decision ${refundDecision.proof_id}`);
      }
    }

    res.status(200).json({ status: "received" });

  } catch (error) {
    console.error("Braintree webhook error:", error);
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
  console.log("Saving Braintree refund decision:", decision);
}

async function updateRefundDecision(idempotencyKey: string, updates: any): Promise<void> {
  // TODO: Implement based on your database
  console.log("Updating Braintree refund decision:", idempotencyKey, updates);
}

async function findRefundDecisionByReference(originalReference: string): Promise<any> {
  // TODO: Implement based on your database
  return null;
}

async function storeBraintreeDecisionMetadata(transactionId: string, metadata: Record<string, string>): Promise<void> {
  // TODO: Implement based on your database
  // Store decision metadata linked to Braintree transaction ID
  console.log(`Storing metadata for transaction ${transactionId}:`, metadata);
}
