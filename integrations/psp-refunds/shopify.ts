// shopify.ts
import { decideRefund, generateIdempotencyKey, truncateJWS, createJWSHash } from "./decide";

export type ShopifyRefundRequest = {
  orderId: string;
  amountMinor: number;
  currency?: string;
  customerCountry?: string;
  customerId?: string;
  reason?: string;
  refundLineItems?: Array<{
    lineItemId: string;
    quantity: number;
    restockType?: "no_restock" | "cancel" | "return" | "legacy_restock";
  }>;
};

export type ShopifyRefundResponse = {
  success: boolean;
  refund_id?: string;
  decision: string;
  proof_id: string;
  certificate_jws: string;
  error?: string;
};

export async function refundShopify(request: ShopifyRefundRequest): Promise<ShopifyRefundResponse> {
  const { orderId, amountMinor, currency = "USD", customerCountry = "US", customerId, reason, refundLineItems } = request;
  const idem = generateIdempotencyKey("shopify", orderId, amountMinor);

  try {
    // Get decision from Contramind
    const d = await decideRefund({
      amount_minor: amountMinor,
      currency,
      psp: "shopify",
      psp_ref: orderId,
      country: customerCountry,
      recent: await countRecentRefunds(customerId, 30),
      reason
    }, idem);

    // Store decision in your database
    await saveRefundDecision({
      psp: "shopify",
      psp_ref: orderId,
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

    // Create Shopify refund
    const refundResult = await createShopifyRefund({
      orderId,
      amountMinor,
      currency,
      proofId: d.proof_id,
      certificateJws: d.certificate_jws,
      refundLineItems,
      reason
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

    // Update database with Shopify refund ID
    await updateRefundDecision(idem, { 
      shopify_refund_id: refundResult.refundId 
    });

    return {
      success: true,
      refund_id: refundResult.refundId,
      decision: d.decision,
      proof_id: d.proof_id,
      certificate_jws: d.certificate_jws
    };

  } catch (error) {
    console.error("Shopify refund error:", error);
    return {
      success: false,
      decision: "ERROR",
      proof_id: "",
      certificate_jws: "",
      error: error instanceof Error ? error.message : "Unknown error"
    };
  }
}

async function createShopifyRefund(params: {
  orderId: string;
  amountMinor: number;
  currency: string;
  proofId: string;
  certificateJws: string;
  refundLineItems?: Array<{
    lineItemId: string;
    quantity: number;
    restockType?: "no_restock" | "cancel" | "return" | "legacy_restock";
  }>;
  reason?: string;
}): Promise<{ success: boolean; refundId?: string; error?: string }> {
  const { orderId, amountMinor, currency, proofId, certificateJws, refundLineItems, reason } = params;

  const shopifyShop = process.env.SHOPIFY_SHOP;
  const shopifyAccessToken = process.env.SHOPIFY_ACCESS_TOKEN;
  const shopifyApiVersion = process.env.SHOPIFY_API_VERSION || "2024-07";

  if (!shopifyShop || !shopifyAccessToken) {
    throw new Error("Shopify shop and access token are required");
  }

  const baseUrl = `https://${shopifyShop}.myshopify.com/admin/api/${shopifyApiVersion}`;

  try {
    // 1. Create the refund
    const refundData: any = {
      refund: {
        currency: currency,
        note: `Contramind decision: ${proofId}`,
        notify: false,
        shipping: {
          full_refund: true
        },
        transactions: [{
          kind: "refund",
          gateway: "bogus", // This will be replaced by Shopify with the actual gateway
          amount: (amountMinor / 100).toFixed(2)
        }]
      }
    };

    // Add refund line items if specified
    if (refundLineItems && refundLineItems.length > 0) {
      refundData.refund.refund_line_items = refundLineItems.map(item => ({
        line_item_id: item.lineItemId,
        quantity: item.quantity,
        restock_type: item.restockType || "no_restock"
      }));
    }

    const refundResponse = await fetch(`${baseUrl}/orders/${orderId}/refunds.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": shopifyAccessToken
      },
      body: JSON.stringify(refundData)
    });

    const refundResult = await refundResponse.json();

    if (!refundResponse.ok) {
      return {
        success: false,
        error: refundResult.errors || `HTTP ${refundResponse.status}`
      };
    }

    const refundId = refundResult.refund.id;

    // 2. Add decision certificate as metafield
    await addShopifyMetafield({
      orderId,
      namespace: "contramind",
      key: "certificate_jws",
      value: truncateJWS(certificateJws, 5000), // Shopify metafield limit
      type: "multi_line_text_field"
    });

    // 3. Add proof ID as metafield
    await addShopifyMetafield({
      orderId,
      namespace: "contramind",
      key: "proof_id",
      value: proofId,
      type: "single_line_text_field"
    });

    // 4. Add decision hash as metafield
    await addShopifyMetafield({
      orderId,
      namespace: "contramind",
      key: "certificate_hash",
      value: createJWSHash(certificateJws),
      type: "single_line_text_field"
    });

    return {
      success: true,
      refundId: refundId
    };

  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Network error"
    };
  }
}

async function addShopifyMetafield(params: {
  orderId: string;
  namespace: string;
  key: string;
  value: string;
  type: string;
}): Promise<void> {
  const { orderId, namespace, key, value, type } = params;

  const shopifyShop = process.env.SHOPIFY_SHOP;
  const shopifyAccessToken = process.env.SHOPIFY_ACCESS_TOKEN;
  const shopifyApiVersion = process.env.SHOPIFY_API_VERSION || "2024-07";

  const baseUrl = `https://${shopifyShop}.myshopify.com/admin/api/${shopifyApiVersion}`;

  const metafieldData = {
    metafield: {
      namespace: namespace,
      key: key,
      value: value,
      type: type
    }
  };

  try {
    const response = await fetch(`${baseUrl}/orders/${orderId}/metafields.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": shopifyAccessToken
      },
      body: JSON.stringify(metafieldData)
    });

    if (!response.ok) {
      const error = await response.json();
      console.warn(`Failed to add metafield ${namespace}.${key}:`, error);
    }

  } catch (error) {
    console.warn(`Error adding metafield ${namespace}.${key}:`, error);
  }
}

// Express.js endpoint example
export async function createShopifyRefundEndpoint(req: any, res: any) {
  try {
    const { 
      orderId, 
      amountCents, 
      currency = "USD", 
      customerCountry = "US", 
      customerId, 
      reason,
      refundLineItems 
    } = req.body;

    if (!orderId || !amountCents) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    const result = await refundShopify({
      orderId,
      amountMinor: amountCents,
      currency,
      customerCountry,
      customerId,
      reason,
      refundLineItems
    });

    if (result.success) {
      res.json(result);
    } else {
      res.status(202).json(result); // 202 for HOLD_HUMAN/REJECT
    }

  } catch (error) {
    console.error("Shopify refund endpoint error:", error);
    res.status(500).json({ 
      error: "Internal server error",
      message: error instanceof Error ? error.message : "Unknown error"
    });
  }
}

// Shopify webhook handler (if using webhooks)
export async function handleShopifyWebhook(req: any, res: any) {
  try {
    const { id, order_id, created_at, processed_at } = req.body;

    if (req.headers['x-shopify-topic'] === 'refunds/create') {
      // Find the refund decision by order ID
      const refundDecision = await findRefundDecisionByReference(order_id.toString());
      
      if (refundDecision) {
        // Update with final Shopify refund ID
        await updateRefundDecision(refundDecision.idempotency_key, {
          shopify_refund_id: id.toString(),
          status: "completed",
          completed_at: new Date().toISOString()
        });

        console.log(`Shopify refund completed: ${id} for decision ${refundDecision.proof_id}`);
      }
    }

    res.status(200).json({ status: "received" });

  } catch (error) {
    console.error("Shopify webhook error:", error);
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
  console.log("Saving Shopify refund decision:", decision);
}

async function updateRefundDecision(idempotencyKey: string, updates: any): Promise<void> {
  // TODO: Implement based on your database
  console.log("Updating Shopify refund decision:", idempotencyKey, updates);
}

async function findRefundDecisionByReference(originalReference: string): Promise<any> {
  // TODO: Implement based on your database
  return null;
}
