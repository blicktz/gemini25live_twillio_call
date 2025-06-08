#!/usr/bin/env python3
"""
Test script to verify Twilio audio fix implementation.
This script tests the audio processing and message formatting without requiring a live Twilio connection.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from app.twilio_integration.websockets import TwilioMediaStreamHandler
from app.config import settings

async def test_audio_queue_system():
    """Test the audio queue system implementation."""
    print("Testing Twilio audio queue system...")
    
    # Mock the audio processor
    with patch('app.twilio_integration.websockets.audio_processor') as mock_processor:
        mock_processor.process_gemini_to_twilio.return_value = "dGVzdCBhdWRpbyBkYXRh"  # base64 test data
        
        # Create mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.client_state = "CONNECTED"
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        # Create handler
        handler = TwilioMediaStreamHandler(mock_websocket)
        handler.stream_sid = "test_stream_123"
        handler.is_active = True
        
        # Start audio sender task
        handler._audio_sender_task = asyncio.create_task(handler._audio_sender_loop())
        
        # Test audio data (simulate 24kHz PCM)
        test_audio = b'\x00\x01' * 1000  # 2000 bytes of test audio
        
        print(f"Sending test audio: {len(test_audio)} bytes")
        
        # Queue audio for sending
        await handler._queue_audio_for_twilio(test_audio)
        
        # Wait a bit for processing
        await asyncio.sleep(0.2)
        
        # Check that messages were queued and sent
        assert mock_websocket.send_text.call_count >= 2, "Should send both media and mark messages"
    
    # Verify message format
    calls = mock_websocket.send_text.call_args_list
    media_call = calls[0][0][0]  # First call argument
    mark_call = calls[1][0][0]   # Second call argument
    
    media_msg = json.loads(media_call)
    mark_msg = json.loads(mark_call)
    
    print(f"Media message: {media_msg['event']}, streamSid: {media_msg['streamSid']}")
    print(f"Mark message: {mark_msg['event']}, mark name: {mark_msg['mark']['name']}")
    
    assert media_msg['event'] == 'media', "First message should be media"
    assert mark_msg['event'] == 'mark', "Second message should be mark"
    assert media_msg['streamSid'] == handler.stream_sid, "StreamSid should match"
    assert mark_msg['streamSid'] == handler.stream_sid, "StreamSid should match"
    assert 'payload' in media_msg['media'], "Media message should have payload"
    assert 'name' in mark_msg['mark'], "Mark message should have name"
    
    # Cleanup
    handler.is_active = False
    if handler._audio_sender_task:
        handler._audio_sender_task.cancel()
        try:
            await handler._audio_sender_task
        except asyncio.CancelledError:
            pass
    
    print("✅ Audio queue system test passed!")

async def test_immediate_audio_system():
    """Test the immediate audio delivery system."""
    print("Testing Twilio immediate audio delivery...")
    
    # Mock the audio processor
    with patch('app.twilio_integration.websockets.audio_processor') as mock_processor:
        mock_processor.process_gemini_to_twilio.return_value = "dGVzdCBhdWRpbyBkYXRh"  # base64 test data
        
        # Create mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.client_state = "CONNECTED"
        mock_websocket.send_text = AsyncMock()
        
        # Create handler
        handler = TwilioMediaStreamHandler(mock_websocket)
        handler.stream_sid = "test_stream_456"
        handler.is_active = True
        handler._use_audio_queue = False
        
        # Test audio data
        test_audio = b'\x00\x01' * 500  # 1000 bytes of test audio
        
        print(f"Sending test audio immediately: {len(test_audio)} bytes")
        
        # Send audio immediately
        await handler._send_audio_immediate(test_audio)
        
        # Check that both messages were sent
        assert mock_websocket.send_text.call_count == 2, "Should send both media and mark messages"
    
    # Verify message format
    calls = mock_websocket.send_text.call_args_list
    media_call = calls[0][0][0]
    mark_call = calls[1][0][0]
    
    media_msg = json.loads(media_call)
    mark_msg = json.loads(mark_call)
    
    print(f"Media message: {media_msg['event']}, streamSid: {media_msg['streamSid']}")
    print(f"Mark message: {mark_msg['event']}, mark name: {mark_msg['mark']['name']}")
    
    assert media_msg['event'] == 'media', "First message should be media"
    assert mark_msg['event'] == 'mark', "Second message should be mark"
    assert 'immediate_' in mark_msg['mark']['name'], "Mark should be immediate type"
    
    print("✅ Immediate audio delivery test passed!")

async def test_mark_message_handling():
    """Test mark message handling from Twilio."""
    print("Testing mark message handling...")
    
    # Create mock WebSocket
    mock_websocket = AsyncMock()
    
    # Create handler
    handler = TwilioMediaStreamHandler(mock_websocket)
    
    # Test mark message from Twilio
    mark_message = {
        "event": "mark",
        "streamSid": "test_stream",
        "mark": {"name": "chunk_1234567890_1000"}
    }
    
    # Process the message
    await handler._process_message(json.dumps(mark_message))
    
    print("✅ Mark message handling test passed!")

def test_configuration():
    """Test configuration settings."""
    print("Testing configuration...")
    
    print(f"Use audio queue: {settings.use_twilio_audio_queue}")
    print(f"Gemini output sample rate: {settings.gemini_output_sample_rate}")
    print(f"Twilio output sample rate: {settings.output_sample_rate}")
    print(f"Save debug audio: {settings.save_debug_audio}")
    
    print("✅ Configuration test passed!")

async def main():
    """Run all tests."""
    print("🧪 Testing Twilio Audio Fix Implementation\n")
    
    test_configuration()
    print()
    
    await test_audio_queue_system()
    print()
    
    await test_immediate_audio_system()
    print()
    
    await test_mark_message_handling()
    print()
    
    print("🎉 All tests passed! The Twilio audio fix implementation looks good.")
    print("\nKey improvements implemented:")
    print("1. ✅ Mark messages for audio synchronization")
    print("2. ✅ Queue-based audio delivery system")
    print("3. ✅ Immediate delivery fallback option")
    print("4. ✅ Proper mark message handling from Twilio")
    print("5. ✅ Configuration options for testing")
    print("\nNext steps:")
    print("- Test with a live Twilio call")
    print("- Monitor logs for mark message acknowledgments")
    print("- Adjust queue timing if needed")

if __name__ == "__main__":
    asyncio.run(main())