"""
Test script for Phase 1 of ADK refactoring.
Tests basic ADK session lifecycle management.
"""

import asyncio
import logging
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.gemini_integration.streaming import GeminiStreamingClient
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_adk_session_lifecycle():
    """Test basic ADK session creation and cleanup."""
    logger.info("=== Testing ADK Session Lifecycle (Phase 1) ===")
    
    try:
        # Create client
        logger.info("1. Creating GeminiStreamingClient...")
        client = GeminiStreamingClient()
        logger.info("✅ Client created successfully")
        
        # Set dummy callbacks
        async def dummy_audio_callback(audio_data: bytes):
            logger.info(f"Received audio: {len(audio_data)} bytes")
        
        async def dummy_text_callback(text: str):
            logger.info(f"Received text: {text}")
        
        logger.info("2. Setting callbacks...")
        client.set_callbacks(dummy_audio_callback, dummy_text_callback)
        logger.info("✅ Callbacks set successfully")
        
        # Start session
        test_session_id = "test_session_123"
        logger.info(f"3. Starting ADK session with ID: {test_session_id}")
        await client.start_session(session_id=test_session_id)
        logger.info("✅ ADK session started successfully")
        
        # Verify session is active
        if client.is_active:
            logger.info("✅ Session is active")
        else:
            logger.error("❌ Session should be active but isn't")
            return False
        
        # Test sending audio chunk (should queue without error)
        logger.info("4. Testing audio chunk queuing...")
        test_audio = b"fake_audio_data_16khz_pcm"
        await client.send_audio_chunk(test_audio)
        logger.info("✅ Audio chunk queued successfully")
        
        # Wait a moment to let the loops process
        logger.info("5. Waiting for processing loops...")
        await asyncio.sleep(2)
        logger.info("✅ Processing loops running")
        
        # Stop session
        logger.info("6. Stopping ADK session...")
        await client.stop_session()
        logger.info("✅ ADK session stopped successfully")
        
        # Verify session is inactive
        if not client.is_active:
            logger.info("✅ Session is inactive")
        else:
            logger.error("❌ Session should be inactive but isn't")
            return False
        
        logger.info("=== Phase 1 Test PASSED ===")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Phase 1 Test FAILED: {e}")
        return False

async def test_multiple_sessions():
    """Test creating and stopping multiple sessions."""
    logger.info("=== Testing Multiple Sessions ===")
    
    try:
        client = GeminiStreamingClient()
        
        # Set callbacks
        async def dummy_audio_callback(audio_data: bytes):
            pass
        async def dummy_text_callback(text: str):
            pass
        client.set_callbacks(dummy_audio_callback, dummy_text_callback)
        
        # Test multiple start/stop cycles
        for i in range(3):
            session_id = f"test_session_{i}"
            logger.info(f"Starting session {i+1}: {session_id}")
            
            await client.start_session(session_id=session_id)
            assert client.is_active, f"Session {i+1} should be active"
            
            await asyncio.sleep(1)  # Brief operation
            
            await client.stop_session()
            assert not client.is_active, f"Session {i+1} should be inactive"
            
            logger.info(f"✅ Session {i+1} lifecycle completed")
        
        logger.info("=== Multiple Sessions Test PASSED ===")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Multiple Sessions Test FAILED: {e}")
        return False

async def main():
    """Run all Phase 1 tests."""
    logger.info("Starting Phase 1 ADK Tests...")
    
    # Check configuration
    logger.info(f"Using Gemini model: {settings.gemini_model}")
    logger.info(f"Google Cloud Project: {settings.google_cloud_project}")
    logger.info(f"Voice name: {settings.gemini_voice_name or 'Puck (default)'}")
    
    tests = [
        test_adk_session_lifecycle,
        test_multiple_sessions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            logger.info("-" * 50)
        except Exception as e:
            logger.exception(f"Test {test.__name__} failed with exception: {e}")
    
    logger.info(f"=== FINAL RESULTS ===")
    logger.info(f"Passed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All Phase 1 tests PASSED!")
        return True
    else:
        logger.error("❌ Some Phase 1 tests FAILED!")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)