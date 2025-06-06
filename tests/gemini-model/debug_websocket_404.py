#!/usr/bin/env python3
"""
Debug script to investigate HTTP 404 error during WebSocket connection.
Tests different regions and captures the actual WebSocket URL being used.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
import google.genai as genai
from google.genai.types import LiveConnectConfig

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test different regions where Gemini 2.0 might be available
TEST_REGIONS = [
    "us-central1",
    "us-east1", 
    "us-west1",
    "europe-west1",
    "asia-southeast1"
]

# Test different model names
TEST_MODELS = [
    "gemini-2.0-flash-live-preview-04-09",
    "gemini-2.0-flash-live-preview",
    "gemini-2.0-flash-live",
    "gemini-2.0-live-preview",
    "gemini-2.0-flash-exp"
]

async def test_websocket_connection(project_id: str, location: str, model_name: str):
    """Test WebSocket connection with specific project, location, and model."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {model_name} in {location}")
    logger.info(f"{'='*60}")
    
    try:
        # Initialize client with specific location
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )
        
        logger.info(f"✅ Client initialized for {location}")
        
        # Create session config
        session_config = LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=genai.types.SpeechConfig(
                voice_config=genai.types.VoiceConfig(
                    prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            )
        )
        
        # Try to create the connection context manager
        logger.info(f"Creating connection context manager...")
        session_context_manager = client.aio.live.connect(
            model=model_name,
            config=session_config
        )
        
        logger.info(f"✅ Connection context manager created")
        
        # Try to establish the actual WebSocket connection
        logger.info(f"Attempting WebSocket connection...")
        try:
            async with session_context_manager as session:
                logger.info(f"🎉 SUCCESS: WebSocket connected for {model_name} in {location}")
                return True, None
        except Exception as ws_error:
            error_msg = str(ws_error)
            logger.error(f"❌ WebSocket connection failed: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Client initialization failed: {error_msg}")
        return False, error_msg

async def debug_websocket_url():
    """Try to capture the actual WebSocket URL being constructed."""
    logger.info(f"\n{'='*60}")
    logger.info(f"DEBUGGING WEBSOCKET URL CONSTRUCTION")
    logger.info(f"{'='*60}")
    
    try:
        # Monkey patch websockets.connect to capture the URL
        import websockets
        original_connect = websockets.connect
        captured_urls = []
        
        def patched_connect(uri, *args, **kwargs):
            captured_urls.append(uri)
            logger.info(f"🔍 WebSocket URL being used: {uri}")
            return original_connect(uri, *args, **kwargs)
        
        websockets.connect = patched_connect
        
        # Now try the connection
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location
        )
        
        session_config = LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=genai.types.SpeechConfig(
                voice_config=genai.types.VoiceConfig(
                    prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            )
        )
        
        session_context_manager = client.aio.live.connect(
            model=settings.gemini_model,
            config=session_config
        )
        
        try:
            async with session_context_manager as session:
                logger.info(f"Connection successful!")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
        
        # Restore original function
        websockets.connect = original_connect
        
        if captured_urls:
            logger.info(f"📋 Captured WebSocket URLs:")
            for url in captured_urls:
                logger.info(f"   {url}")
        else:
            logger.warning(f"⚠️  No WebSocket URLs captured")
            
    except Exception as e:
        logger.error(f"❌ URL debugging failed: {e}")

async def main():
    """Main debugging function."""
    logger.info(f"🚀 Starting WebSocket 404 debugging")
    logger.info(f"Current settings:")
    logger.info(f"  - Project: {settings.google_cloud_project}")
    logger.info(f"  - Location: {settings.google_cloud_location}")
    logger.info(f"  - Model: {settings.gemini_model}")
    
    # First, try to capture the WebSocket URL
    await debug_websocket_url()
    
    # Test current configuration
    logger.info(f"\n{'='*60}")
    logger.info(f"TESTING CURRENT CONFIGURATION")
    logger.info(f"{'='*60}")
    
    success, error = await test_websocket_connection(
        settings.google_cloud_project,
        settings.google_cloud_location,
        settings.gemini_model
    )
    
    if success:
        logger.info(f"🎉 Current configuration works!")
        return
    
    logger.info(f"❌ Current configuration failed: {error}")
    
    # Test different regions with current model
    logger.info(f"\n{'='*60}")
    logger.info(f"TESTING DIFFERENT REGIONS")
    logger.info(f"{'='*60}")
    
    working_configs = []
    
    for region in TEST_REGIONS:
        if region == settings.google_cloud_location:
            continue  # Already tested
            
        success, error = await test_websocket_connection(
            settings.google_cloud_project,
            region,
            settings.gemini_model
        )
        
        if success:
            working_configs.append((region, settings.gemini_model))
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    # Test different model names in current region
    logger.info(f"\n{'='*60}")
    logger.info(f"TESTING DIFFERENT MODEL NAMES")
    logger.info(f"{'='*60}")
    
    for model in TEST_MODELS:
        if model == settings.gemini_model:
            continue  # Already tested
            
        success, error = await test_websocket_connection(
            settings.google_cloud_project,
            settings.google_cloud_location,
            model
        )
        
        if success:
            working_configs.append((settings.google_cloud_location, model))
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    # Report results
    logger.info(f"\n{'='*60}")
    logger.info(f"DEBUGGING RESULTS")
    logger.info(f"{'='*60}")
    
    if working_configs:
        logger.info(f"🎉 Found working configurations:")
        for region, model in working_configs:
            logger.info(f"   ✅ Region: {region}, Model: {model}")
        
        # Suggest the first working config
        best_region, best_model = working_configs[0]
        logger.info(f"\n💡 RECOMMENDATION:")
        logger.info(f"   Update .env file with:")
        logger.info(f"   GOOGLE_CLOUD_LOCATION={best_region}")
        logger.info(f"   GEMINI_MODEL={best_model}")
    else:
        logger.error(f"❌ No working configurations found!")
        logger.error(f"   This suggests the Live API might require special access")
        logger.error(f"   or the model names/regions tested are incorrect.")

if __name__ == "__main__":
    asyncio.run(main())