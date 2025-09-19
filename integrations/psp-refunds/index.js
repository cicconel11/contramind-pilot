// index.js - Main entry point for PSP refund integrations

export { decideRefund, generateIdempotencyKey, truncateJWS, createJWSHash } from './decide.js';
export { refundStripe, createStripeRefundEndpoint } from './stripe.js';
export { refundAdyen, createAdyenRefundEndpoint, handleAdyenRefundWebhook } from './adyen.js';
export { refundBraintree, createBraintreeRefundEndpoint, handleBraintreeWebhook } from './braintree.js';
export { refundShopify, createShopifyRefundEndpoint, handleShopifyWebhook } from './shopify.js';
export { verifyCertificate } from './verify-cert.js';

// Express.js app example
import express from 'express';
import { 
  createStripeRefundEndpoint,
  createAdyenRefundEndpoint,
  createBraintreeRefundEndpoint,
  createShopifyRefundEndpoint
} from './index.js';

const app = express();
app.use(express.json());

// PSP refund endpoints
app.post('/refunds/stripe', createStripeRefundEndpoint);
app.post('/refunds/adyen', createAdyenRefundEndpoint);
app.post('/refunds/braintree', createBraintreeRefundEndpoint);
app.post('/refunds/shopify', createShopifyRefundEndpoint);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

export default app;
