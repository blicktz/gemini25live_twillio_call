#!/usr/bin/env python3
"""
Test script to verify the Gemini Live API WebSocket connection works.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_live_session_connection():
    """Test that we can establish a Live API session without WebSocket errors."""
    try:
        logger.info("Testing Gemini Live API session connection...")
        
        # Import after setting up the path
        from app.gemini_integration.streaming import GeminiStreamingClient
        
        # Initialize the client
        client = GeminiStreamingClient()
        logger.info("✅ Gemini client initialized")
        
        # Set up dummy callbacks
        async def audio_callback(audio_data: bytes):
            logger.info(f"Received audio data: {len(audio_data)} bytes")
        
        async def text_callback(text: str):
            logger.info(f"Received text: {text}")
        
        client.set_callbacks(audio_callback, text_callback)
        
        # Try to start a session
        logger.info("Attempting to start Live API session...")
        await client.start_session("Hello, this is a test connection.")
        
        logger.info("✅ Live API session started successfully!")
        
        # Let it run for a few seconds to ensure stability
        await asyncio.sleep(3)
        
        # Stop the session
        logger.info("Stopping Live API session...")
        await client.stop_session()
        
        logger.info("✅ Live API session stopped successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to establish Live API session: {e}")
        logger.exception("Full traceback:")
        return False

async def main():
    """Run the test."""
    logger.info("🚀 Starting Gemini Live API WebSocket connection test")
    
    # Test session connection
    success = await test_live_session_connection()
    
    if success:
        logger.info("🎉 WebSocket connection test passed! The 1007 error has been fixed.")
        return True
    else:
        logger.error("💥 WebSocket connection test failed.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)