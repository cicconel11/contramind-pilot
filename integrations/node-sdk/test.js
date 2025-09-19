import ContramindDecider from "./index.js";

async function test() {
  const decider = new ContramindDecider();
  
  console.log("🧪 Testing Contramind Decider SDK...");
  
  try {
    // Test basic decision
    const result = await decider.decide({
      amount: 1500.0,
      country: "US",
      ts: new Date().toISOString(),
      recent: 1,
      context_id: "test_sdk"
    });
    
    console.log("✅ Decision result:", {
      decision: result.decision,
      verified: result.verified,
      proofId: result.proof_id,
      obligations: result.obligations
    });
    
    // Test certificate verification
    if (result.certificate_jws) {
      const verified = await decider.verifyCertificate(result.certificate_jws);
      console.log("✅ Certificate verified:", verified.payload.sub);
    }
    
    // Test idempotency
    const result2 = await decider.decide({
      amount: 1500.0,
      country: "US", 
      ts: new Date().toISOString(),
      recent: 1,
      context_id: "test_sdk"
    }, "test-idempotency-key");
    
    const result3 = await decider.decide({
      amount: 1500.0,
      country: "US",
      ts: new Date().toISOString(), 
      recent: 1,
      context_id: "test_sdk"
    }, "test-idempotency-key");
    
    if (result2.proof_id === result3.proof_id) {
      console.log("✅ Idempotency working");
    } else {
      console.log("❌ Idempotency failed");
    }
    
    console.log("🎉 All tests passed!");
    
  } catch (error) {
    console.error("❌ Test failed:", error.message);
  }
}

test();
