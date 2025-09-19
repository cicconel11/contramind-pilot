#!/usr/bin/env node
// test-all.js - Test all PSP integrations

import { decideRefund, generateIdempotencyKey } from './decide.js';
import { verifyCertificate } from './verify-cert.js';

async function testDecideAPI() {
  console.log("🧪 Testing Contramind Decision API...");
  
  try {
    const result = await decideRefund({
      amount_minor: 1500, // $15.00
      currency: "USD",
      psp: "stripe",
      psp_ref: "ch_test_123",
      country: "US",
      recent: 1
    });
    
    console.log("✅ Decision result:", {
      decision: result.decision,
      proof_id: result.proof_id,
      obligations: result.obligations
    });
    
    return result;
    
  } catch (error) {
    console.error("❌ Decision API test failed:", error.message);
    return null;
  }
}

async function testCertificateVerification(certificateJws) {
  console.log("🔐 Testing certificate verification...");
  
  try {
    const result = await verifyCertificate(certificateJws);
    
    if (result.valid) {
      console.log("✅ Certificate verification successful");
      console.log("   Decision:", result.payload.decision);
      console.log("   Proof ID:", result.payload.proof_id);
      console.log("   Key ID:", result.kid);
    } else {
      console.error("❌ Certificate verification failed:", result.error);
    }
    
    return result.valid;
    
  } catch (error) {
    console.error("❌ Certificate verification test failed:", error.message);
    return false;
  }
}

async function testIdempotency() {
  console.log("🔄 Testing idempotency...");
  
  const idemKey = generateIdempotencyKey("stripe", "ch_test_123", 1500);
  
  try {
    const result1 = await decideRefund({
      amount_minor: 1500,
      currency: "USD",
      psp: "stripe",
      psp_ref: "ch_test_123",
      country: "US",
      recent: 1
    }, idemKey);
    
    const result2 = await decideRefund({
      amount_minor: 1500,
      currency: "USD",
      psp: "stripe",
      psp_ref: "ch_test_123",
      country: "US",
      recent: 1
    }, idemKey);
    
    if (result1.proof_id === result2.proof_id) {
      console.log("✅ Idempotency working correctly");
      return true;
    } else {
      console.error("❌ Idempotency failed - different proof IDs");
      return false;
    }
    
  } catch (error) {
    console.error("❌ Idempotency test failed:", error.message);
    return false;
  }
}

async function runAllTests() {
  console.log("🚀 Running PSP Refund Integration Tests\n");
  
  // Test 1: Decision API
  const decisionResult = await testDecideAPI();
  if (!decisionResult) {
    console.log("\n❌ Tests failed - Decision API not available");
    process.exit(1);
  }
  
  console.log();
  
  // Test 2: Certificate verification
  const verificationPassed = await testCertificateVerification(decisionResult.certificate_jws);
  
  console.log();
  
  // Test 3: Idempotency
  const idempotencyPassed = await testIdempotency();
  
  console.log();
  
  // Summary
  if (verificationPassed && idempotencyPassed) {
    console.log("🎉 All tests passed! PSP integrations are ready to use.");
    console.log("\n📋 Next steps:");
    console.log("   1. Configure your PSP credentials in environment variables");
    console.log("   2. Implement database helpers for your specific setup");
    console.log("   3. Deploy to staging and test with real PSP webhooks");
    console.log("   4. Start with shadow mode (log decisions, don't act on them)");
    console.log("   5. Gradually roll out to production traffic");
  } else {
    console.log("❌ Some tests failed. Check the Contramind services are running.");
    process.exit(1);
  }
}

// Run tests if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests().catch(console.error);
}
