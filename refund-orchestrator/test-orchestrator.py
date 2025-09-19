#!/usr/bin/env python3
"""
Test script for the Refund Orchestrator
"""
import asyncio
import httpx
import json
import os
from typing import Dict, Any

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8085")

async def test_health():
    """Test health endpoint"""
    print("🏥 Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{ORCHESTRATOR_URL}/healthz")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

async def test_stripe_refund():
    """Test Stripe refund endpoint"""
    print("\n💳 Testing Stripe refund...")
    payload = {
        "amount_minor": 1500,  # $15.00
        "currency": "USD",
        "psp_ref": "pi_test_123",
        "country": "US",
        "recent": 1
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/refund/stripe",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Stripe refund successful: {data}")
                return True
            else:
                print(f"❌ Stripe refund failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Stripe refund error: {e}")
            return False

async def test_adyen_refund():
    """Test Adyen refund endpoint"""
    print("\n🌍 Testing Adyen refund...")
    payload = {
        "amount_minor": 1500,  # $15.00
        "currency": "USD",
        "psp_ref": "test_psp_ref_123",
        "country": "US",
        "recent": 0
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/refund/adyen",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Adyen refund successful: {data}")
                return True
            else:
                print(f"❌ Adyen refund failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Adyen refund error: {e}")
            return False

async def test_braintree_refund():
    """Test Braintree refund endpoint"""
    print("\n🧠 Testing Braintree refund...")
    payload = {
        "amount_minor": 1500,  # $15.00
        "currency": "USD",
        "psp_ref": "test_txn_123",
        "country": "US",
        "recent": 0
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/refund/braintree",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Braintree refund successful: {data}")
                return True
            else:
                print(f"❌ Braintree refund failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Braintree refund error: {e}")
            return False

async def test_shopify_refund():
    """Test Shopify refund endpoint"""
    print("\n🛍️ Testing Shopify refund...")
    payload = {
        "amount_minor": 1500,  # $15.00
        "currency": "USD",
        "psp_ref": "1234567890",
        "country": "US",
        "recent": 0
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/refund/shopify",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Shopify refund successful: {data}")
                return True
            else:
                print(f"❌ Shopify refund failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Shopify refund error: {e}")
            return False

async def test_idempotency():
    """Test idempotency across multiple requests"""
    print("\n🔄 Testing idempotency...")
    payload = {
        "amount_minor": 2000,  # $20.00
        "currency": "USD",
        "psp_ref": "idem_test_123",
        "country": "US",
        "recent": 0
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # First request
            response1 = await client.post(
                f"{ORCHESTRATOR_URL}/refund/stripe",
                json=payload,
                timeout=30.0
            )
            
            # Second request (should be identical)
            response2 = await client.post(
                f"{ORCHESTRATOR_URL}/refund/stripe",
                json=payload,
                timeout=30.0
            )
            
            if response1.status_code == 200 and response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                
                if data1.get("proof_id") == data2.get("proof_id"):
                    print("✅ Idempotency working correctly")
                    return True
                else:
                    print("❌ Idempotency failed - different proof IDs")
                    return False
            else:
                print(f"❌ Idempotency test failed: {response1.status_code}, {response2.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Idempotency test error: {e}")
            return False

async def run_all_tests():
    """Run all tests"""
    print("🚀 Running Refund Orchestrator Tests\n")
    
    tests = [
        ("Health Check", test_health),
        ("Stripe Refund", test_stripe_refund),
        ("Adyen Refund", test_adyen_refund),
        ("Braintree Refund", test_braintree_refund),
        ("Shopify Refund", test_shopify_refund),
        ("Idempotency", test_idempotency),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Refund Orchestrator is ready for production.")
    else:
        print("⚠️ Some tests failed. Check the Contramind services are running.")
        print("\n💡 Troubleshooting:")
        print("   1. Ensure Contramind services are running (decider, attestor)")
        print("   2. Check environment variables are set correctly")
        print("   3. Verify PSP credentials are configured")
        print("   4. Check network connectivity to external PSP APIs")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
