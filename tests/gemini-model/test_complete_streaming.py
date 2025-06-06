#!/usr/bin/env python3
"""
Test complete streaming integration with initial prompt sending
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.gemini_integration.streaming import GeminiStreamingClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_complete_streaming():
    """Test the complete streaming integration with initial prompt"""
    
    logger.info("🧪 Testing complete streaming integration...")
    
    try:
        # Initialize the streaming client
        client = GeminiStreamingClient()
        
        # Test initial prompt
        initial_prompt = "Hello! Please introduce yourself briefly."
        
        logger.info(f"📤 Testing with initial prompt: '{initial_prompt}'")
        
        # Start streaming session
        await client.start_session(initial_prompt=initial_prompt)
        
        logger.info("✅ Streaming session started successfully")
        
        # Listen for a few responses
        response_count = 0
        max_responses = 3
        
        logger.info(f"� Listening for up to {max_responses} responses...")
        
        async for response in client.listen_for_responses():
            response_count += 1
            logger.info(f"� Response {response_count}: {response}")
            
            if response_count >= max_responses:
                logger.info(f"✅ Received {max_responses} responses, stopping test")
                break
        
        # Clean up
        await client.stop_streaming()
        logger.info("🧹 Streaming session stopped")
        
        logger.info("✅ Complete streaming integration test successful!")
        
    except Exception as e:
        logger.error(f"❌ Complete streaming integration test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_complete_streaming())