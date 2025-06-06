#!/usr/bin/env python3
"""
Script to inspect the Live API session object and find correct methods.
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

async def inspect_live_api():
    """Inspect the Live API session object to find available methods."""
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
            logger.info("🔍 Inspecting Live API session object:")
            logger.info(f"Session type: {type(session)}")
            logger.info(f"Session dir: {[attr for attr in dir(session) if not attr.startswith('_')]}")
            
            # Check for send-related methods
            send_methods = [attr for attr in dir(session) if 'send' in attr.lower()]
            logger.info(f"Send-related methods: {send_methods}")
            
            # Check for message/content methods
            content_methods = [attr for attr in dir(session) if any(word in attr.lower() for word in ['message', 'content', 'text', 'prompt'])]
            logger.info(f"Content-related methods: {content_methods}")
            
            # Try to get method signatures
            for method_name in ['send', 'send_text', 'send_message']:
                if hasattr(session, method_name):
                    method = getattr(session, method_name)
                    logger.info(f"Method {method_name}: {method}")
                    logger.info(f"Method {method_name} signature: {method.__doc__ if hasattr(method, '__doc__') else 'No docs'}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to inspect Live API: {e}")
        logger.exception("Full traceback:")
        return False

if __name__ == "__main__":
    success = asyncio.run(inspect_live_api())
    sys.exit(0 if success else 1)