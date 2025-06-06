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