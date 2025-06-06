#!/usr/bin/env python3
"""
Comprehensive integration test runner for AI Call Answering Service.
"""

import requests
import json
import time
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_health_endpoints() -> bool:
    """Test health check endpoints."""
    print("🔍 Testing health endpoints...")
    
    # Test root endpoint
    try:
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "status" in data
        print("✅ Root endpoint test passed")
    except Exception as e:
        print(f"❌ Root endpoint test failed: {e}")
        return False
    
    # Test health endpoint
    try:
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health endpoint test passed")
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False
    
    return True

def test_twilio_webhooks() -> bool:
    """Test Twilio webhook endpoints."""
    print("🔍 Testing Twilio webhooks...")
    
    # Test voice webhook
    try:
        webhook_data = {
            "CallSid": "CA1234567890abcdef1234567890abcdef",
            "From": "+15551234567",
            "To": "+15559876543",
            "CallStatus": "ringing",
            "Direction": "inbound",
            "AccountSid": "AC1234567890abcdef1234567890abcdef"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/twilio-voice",
            data=webhook_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 200
        assert "application/xml" in response.headers.get("content-type", "")
        assert "<Say>" in response.text
        assert "<Stream>" in response.text
        print("✅ Voice webhook test passed")
    except Exception as e:
        print(f"❌ Voice webhook test failed: {e}")
        return False
    
    # Test status webhook
    try:
        status_data = {
            "CallSid": "CA1234567890abcdef1234567890abcdef",
            "CallStatus": "completed"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/twilio-status",
            data=status_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print("✅ Status webhook test passed")
    except Exception as e:
        print(f"❌ Status webhook test failed: {e}")
        return False
    
    return True

def check_server_running() -> bool:
    """Check if the server is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Run all integration tests."""
    print("🚀 Starting AI Call Answering Service Integration Tests")
    print(f"📍 Testing server at: {BASE_URL}")
    
    # Check if server is running
    if not check_server_running():
        print("❌ Server is not running. Please start the server first:")
        print("   python -m app.main")
        sys.exit(1)
    
    print("✅ Server is running")
    
    # Run tests
    tests = [
        ("Health Endpoints", test_health_endpoints),
        ("Twilio Webhooks", test_twilio_webhooks),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} tests...")
        if test_func():
            passed += 1
            print(f"✅ {test_name} tests passed")
        else:
            print(f"❌ {test_name} tests failed")
    
    print(f"\n📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()