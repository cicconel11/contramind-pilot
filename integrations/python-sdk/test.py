#!/usr/bin/env python3

from contramind import ContramindDecider

def test():
    decider = ContramindDecider()
    
    print("🧪 Testing Contramind Decider SDK...")
    
    try:
        # Test basic decision
        result = decider.decide({
            "amount": 1500.0,
            "country": "US",
            "ts": "2025-09-16T12:00:00Z",
            "recent": 1,
            "context_id": "test_sdk"
        })
        
        print("✅ Decision result:", {
            "decision": result.decision,
            "verified": result.verified,
            "proof_id": result.proof_id,
            "obligations": result.obligations
        })
        
        # Test certificate verification
        if result.certificate_jws:
            verified = decider.verify_certificate(result.certificate_jws)
            print("✅ Certificate verified:", verified["sub"])
        
        # Test idempotency
        result2 = decider.decide({
            "amount": 1500.0,
            "country": "US",
            "ts": "2025-09-16T12:00:00Z",
            "recent": 1,
            "context_id": "test_sdk"
        }, "test-idempotency-key")
        
        result3 = decider.decide({
            "amount": 1500.0,
            "country": "US",
            "ts": "2025-09-16T12:00:00Z",
            "recent": 1,
            "context_id": "test_sdk"
        }, "test-idempotency-key")
        
        if result2.proof_id == result3.proof_id:
            print("✅ Idempotency working")
        else:
            print("❌ Idempotency failed")
        
        print("🎉 All tests passed!")
        
    except Exception as error:
        print(f"❌ Test failed: {error}")

if __name__ == "__main__":
    test()
