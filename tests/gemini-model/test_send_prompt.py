#!/usr/bin/env python3
"""
Test script to verify the correct way to send initial prompt to Live API.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.config import settings
from google import genai
from google.genai.types import LiveConnectConfig, SpeechConfig, VoiceConfig, PrebuiltVoiceConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_send_prompt():
    """Test sending initial prompt to Live API session."""
    try:
        # Initialize client
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location
        )
        
        # Create session config
        session_config = LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            )
        )
        
        # Connect to Live API
        session_context_manager = client.aio.live.connect(
            model=settings.gemini_model,
            config=session_config
        )
        
        async with session_context_manager as session:
            logger.info("✅ Connected to Live API")
            
            # Test different ways to send initial prompt
            initial_prompt = "You are a helpful voice assistant for phone calls. Please respond briefly and naturally."
            
            # Method 1: Send as simple string
            logger.info("🧪 Testing Method 1: Send as string")
            try:
                await session.send(input=initial_prompt, end_of_turn=True)
                logger.info("✅ Method 1 successful: String input")
            except Exception as e:
                logger.error(f"❌ Method 1 failed: {e}")
            
            # Method 2: Send without end_of_turn parameter
            logger.info("🧪 Testing Method 2: Send without end_of_turn")
            try:
                await session.send(input="Test message without end_of_turn")
                logger.info("✅ Method 2 successful: No end_of_turn")
            except Exception as e:
                logger.error(f"❌ Method 2 failed: {e}")
            
            # Listen for responses
            logger.info("👂 Listening for responses...")
            response_count = 0
            async for message in session.receive():
                response_count += 1
                logger.info(f"📨 Response {response_count}: {message}")
                if response_count >= 3:  # Limit responses to avoid infinite loop
                    break
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to test send prompt: {e}")
        logger.exception("Full traceback:")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_send_prompt())
    sys.exit(0 if success else 1)