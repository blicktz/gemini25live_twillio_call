#!/usr/bin/env python3
"""
Comprehensive integration test runner for AI Call Answering Service.
"""

import requests
import json
import time
import sys
import os
import hmac
import hashlib
import base64
from urllib.parse import urlencode
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_URL = "http://localhost:8000"

def generate_twilio_signature(url: str, params: Dict[str, str], auth_token: str) -> str:
    """Generate a valid Twilio signature for webhook validation.
    
    Args:
        url: The full URL of the webhook endpoint
        params: The form parameters being sent
        auth_token: The Twilio auth token
        
    Returns:
        Base64-encoded HMAC-SHA1 signature
    """
    # Sort parameters and create query string
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params)
    
    # Create the signature string: URL + sorted parameters
    signature_string = url + query_string
    
    # Generate HMAC-SHA1 signature
    signature = hmac.new(
        auth_token.encode('utf-8'),
        signature_string.encode('utf-8'),
        hashlib.sha1
    ).digest()
    
    # Return base64-encoded signature
    return base64.b64encode(signature).decode('utf-8')

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
            "AccountSid": "xxx"
        }
        
        # Get Twilio auth token from environment (should match server config)
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        print(f"   Using auth token: {auth_token[:10]}...")
        
        # Generate Twilio signature
        webhook_url = f"{BASE_URL}/api/v1/twilio-voice"
        signature = generate_twilio_signature(webhook_url, webhook_data, auth_token)
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature
        }
        
        response = requests.post(
            webhook_url,
            data=webhook_data,
            headers=headers
        )
        
        print(f"   Response status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")
        print(f"   Response content: {response.text}")
        
        # Check each assertion individually for better debugging
        print(f"   Checking status code: {response.status_code == 200}")
        assert response.status_code == 200
        
        content_type = response.headers.get("content-type", "")
        print(f"   Checking content-type: 'application/xml' in '{content_type}' = {'application/xml' in content_type}")
        assert "application/xml" in content_type
        
        print(f"   Checking <Say tag: {'<Say' in response.text}")
        assert "<Say" in response.text  # Match both <Say> and <Say voice="...">
        
        print(f"   Checking <Stream tag: {'<Stream' in response.text}")
        assert "<Stream" in response.text  # Match both <Stream> and <Stream />
        
        print("✅ Voice webhook test passed")
    except Exception as e:
        print(f"❌ Voice webhook test failed: {e}")
        print(f"   Response status code: {getattr(e, 'response', {}).get('status_code', 'N/A')}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"   Response content: {e.response.text}")
        return False
    
    # Test status webhook
    try:
        status_data = {
            "CallSid": "CA1234567890abcdef1234567890abcdef",
            "CallStatus": "completed"
        }
        
        # Get Twilio auth token from environment (should match server config)
        auth_token = os.getenv('TWILIO_AUTH_TOKEN', '95e0c91978c694d76facc168c7ec1bec')
        
        # Generate Twilio signature
        status_url = f"{BASE_URL}/api/v1/twilio-status"
        signature = generate_twilio_signature(status_url, status_data, auth_token)
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature
        }
        
        response = requests.post(
            status_url,
            data=status_data,
            headers=headers
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