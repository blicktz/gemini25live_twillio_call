# Integration Test Plan for AI Call Answering Service

This document provides a comprehensive test plan for locally testing the AI Call Answering Service using curl commands and Python scripts.

## Prerequisites

1. **Start the FastAPI server**:
   ```bash
   cd /path/to/twillio_gemini25
   python -m app.main
   ```
   Server should be running on `http://localhost:8000`

2. **Environment Setup**:
   - Copy `.env.example` to `.env`
   - Fill in required API keys (for full testing)
   - For basic endpoint testing, dummy values are sufficient

## Test Cases

### 1. Health Check Endpoints

#### Test 1.1: Root Endpoint
```bash
curl -X GET http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -v
```

**Expected Response:**
```json
{
  "message": "AI Call Answering Service",
  "status": "running",
  "version": "1.0.0"
}
```
**Expected Status Code:** `200 OK`

#### Test 1.2: Health Check Endpoint
```bash
curl -X GET http://localhost:8000/health \
  -H "Content-Type: application/json" \
  -v
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "ai-call-answering",
  "timestamp": "2024-01-01T00:00:00Z"
}
```
**Expected Status Code:** `200 OK`

### 2. Twilio Webhook Endpoints

#### Test 2.1: Incoming Call Webhook
```bash
curl -X POST http://localhost:8000/api/v1/twilio-voice \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=CA1234567890abcdef1234567890abcdef" \
  -d "From=%2B15551234567" \
  -d "To=%2B15559876543" \
  -d "CallStatus=ringing" \
  -d "Direction=inbound" \
  -d "AccountSid=" \
  -v
```

**Expected Response:** TwiML XML containing:
- `<Say>` element with greeting
- `<Start><Stream>` element with WebSocket URL
- `<Pause>` element

**Expected Status Code:** `200 OK`
**Expected Content-Type:** `application/xml`

#### Test 2.2: Call Status Webhook
```bash
curl -X POST http://localhost:8000/api/v1/twilio-status \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=CA1234567890abcdef1234567890abcdef" \
  -d "CallStatus=completed" \
  -v
```

**Expected Response:**
```json
{
  "status": "ok"
}
```
**Expected Status Code:** `200 OK`

### 3. WebSocket Testing

#### Test 3.1: WebSocket Connection Test (Python Script)

Create and run this Python script:

```python
#!/usr/bin/env python3
"""
WebSocket integration test for Twilio media stream endpoint.
"""

import asyncio
import json
import base64
import websockets
from datetime import datetime

async def test_websocket_connection():
    """Test WebSocket connection and message handling."""
    uri = "ws://localhost:8000/ws/media-stream"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # Test 1: Send stream start message
            start_message = {
                "event": "start",
                "start": {
                    "streamSid": "MZ1234567890abcdef1234567890abcdef",
                    "callSid": "CA1234567890abcdef1234567890abcdef",
                    "tracks": ["inbound", "outbound"]
                },
                "streamSid": "MZ1234567890abcdef1234567890abcdef"
            }
            
            await websocket.send(json.dumps(start_message))
            print("✅ Sent stream start message")
            
            # Test 2: Send media message with dummy audio
            # Generate dummy MuLaw audio data (silence)
            dummy_audio = b'\x7f' * 160  # 160 bytes of silence (20ms at 8kHz)
            base64_audio = base64.b64encode(dummy_audio).decode('utf-8')
            
            media_message = {
                "event": "media",
                "sequenceNumber": "1",
                "media": {
                    "track": "inbound",
                    "chunk": "1",
                    "timestamp": "12345",
                    "payload": base64_audio
                },
                "streamSid": "MZ1234567890abcdef1234567890abcdef"
            }
            
            await websocket.send(json.dumps(media_message))
            print("✅ Sent media message with dummy audio")
            
            # Test 3: Listen for any responses (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📨 Received response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received (expected for simulation)")
            
            # Test 4: Send stop message
            stop_message = {
                "event": "stop",
                "streamSid": "MZ1234567890abcdef1234567890abcdef"
            }
            
            await websocket.send(json.dumps(stop_message))
            print("✅ Sent stream stop message")
            
            print("🎉 WebSocket test completed successfully")
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting WebSocket integration test...")
    success = asyncio.run(test_websocket_connection())
    if success:
        print("✅ All WebSocket tests passed")
    else:
        print("❌ WebSocket tests failed")
        exit(1)
```

**Save as:** `tests/integration/test_websocket.py`

**Run with:**
```bash
python tests/integration/test_websocket.py
```

**Expected Output:**
- Successful WebSocket connection
- Messages sent without errors
- Graceful handling of stream start, media, and stop events
- No crashes or exceptions

### 4. Error Handling Tests

#### Test 4.1: Invalid Webhook Data
```bash
curl -X POST http://localhost:8000/api/v1/twilio-voice \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "InvalidField=test" \
  -v
```

**Expected Response:** TwiML with error message
**Expected Status Code:** `200 OK` (graceful error handling)

#### Test 4.2: Missing Content-Type
```bash
curl -X POST http://localhost:8000/api/v1/twilio-voice \
  -d "CallSid=test" \
  -v
```

**Expected Response:** Should handle gracefully
**Expected Status Code:** `200 OK` or `422 Unprocessable Entity`

### 5. Load Testing (Optional)

#### Test 5.1: Concurrent Health Checks
```bash
# Run multiple concurrent requests
for i in {1..10}; do
  curl -X GET http://localhost:8000/health &
done
wait
```

**Expected Result:** All requests should complete successfully

### 6. Integration Test Script

Create a comprehensive test runner:

```python
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
            "AccountSid": ""
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
```

**Save as:** `tests/integration/run_tests.py`

**Run with:**
```bash
python tests/integration/run_tests.py
```

## Test Execution Order

1. **Start the server**: `python -m app.main`
2. **Run basic tests**: `python tests/integration/run_tests.py`
3. **Test WebSocket**: `python tests/integration/test_websocket.py`
4. **Manual curl tests**: Run individual curl commands as needed

## Expected Results Summary

| Test Category | Expected Outcome |
|---------------|------------------|
| Health Endpoints | 200 OK with JSON responses |
| Twilio Webhooks | 200 OK with TwiML/JSON responses |
| WebSocket Connection | Successful connection and message handling |
| Error Handling | Graceful error responses |
| Load Testing | All concurrent requests succeed |

## Troubleshooting

### Common Issues

1. **Connection Refused**:
   - Ensure server is running on port 8000
   - Check firewall settings

2. **WebSocket Connection Failed**:
   - Verify WebSocket endpoint is accessible
   - Check for proxy/firewall blocking WebSocket connections

3. **Invalid TwiML Response**:
   - Check server logs for errors
   - Verify webhook data format

4. **Environment Variables**:
   - For full functionality, ensure `.env` file has valid API keys
   - For basic testing, dummy values are sufficient

### Debugging Tips

1. **Enable Debug Mode**:
   ```bash
   export DEBUG=true
   python -m app.main
   ```

2. **Check Server Logs**:
   - Monitor console output for errors
   - Look for audio processing pipeline logs

3. **Verbose Curl**:
   ```bash
   curl -v -X GET http://localhost:8000/health
   ```

4. **Network Testing**:
   ```bash
   # Test if port is open
   nc -zv localhost 8000
   ```

## Notes

- These tests focus on API endpoints and basic functionality
- Full audio processing requires valid Gemini API keys
- WebSocket tests simulate Twilio media stream format
- Production testing should include real Twilio phone numbers
- Consider adding automated CI/CD pipeline integration