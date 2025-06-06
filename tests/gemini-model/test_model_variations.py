#!/usr/bin/env python3
"""
Test different model names and regions for Gemini Live API
"""
import asyncio
import logging
from app.gemini_integration.streaming import GeminiStreamingClient
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model variations to test
MODEL_VARIATIONS = [
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-thinking-exp-1219",
    "gemini-exp-1206",
    "gemini-2.5-flash-preview-native-audio-dialog",
    "models/gemini-2.0-flash-exp",
    "models/gemini-2.5-flash-preview-native-audio-dialog"
]

# Region variations to test
REGION_VARIATIONS = [
    "us-central1",
    "us-east1", 
    "us-west1",
    "europe-west1"
]

async def test_model_region_combination(model_name: str, region: str):
    """Test a specific model and region combination"""
    logger.info(f"\n🧪 Testing model: {model_name} in region: {region}")
    
    # Temporarily override settings
    original_model = settings.gemini_model
    original_location = settings.google_cloud_location
    
    try:
        settings.gemini_model = model_name
        settings.google_cloud_location = region
        
        client = GeminiStreamingClient(model_name=model_name)
        
        # Try to start session (this will fail at WebSocket connection if model/region is wrong)
        await client.start_session("Test connection")
        
        logger.info(f"✅ SUCCESS: {model_name} works in {region}")
        await client.stop_session()
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "HTTP 404" in error_msg:
            logger.info(f"❌ 404 Error: {model_name} not available in {region}")
        elif "Invalid JWT Signature" in error_msg:
            logger.info(f"❌ Auth Error: {model_name} - credentials issue")
        else:
            logger.info(f"❌ Other Error: {model_name} in {region} - {error_msg}")
        return False
    finally:
        # Restore original settings
        settings.gemini_model = original_model
        settings.google_cloud_location = original_location

async def main():
    logger.info("🔍 Testing Gemini Live API model and region combinations")
    logger.info("=" * 60)
    
    successful_combinations = []
    
    # Test a few key combinations first
    priority_tests = [
        ("gemini-2.0-flash-exp", "us-central1"),
        ("gemini-exp-1206", "us-central1"),
        ("models/gemini-2.0-flash-exp", "us-central1"),
    ]
    
    for model, region in priority_tests:
        success = await test_model_region_combination(model, region)
        if success:
            successful_combinations.append((model, region))
            logger.info(f"🎉 Found working combination: {model} in {region}")
            break  # Stop on first success
    
    if successful_combinations:
        model, region = successful_combinations[0]
        logger.info(f"\n✅ RECOMMENDED CONFIGURATION:")
        logger.info(f"   GEMINI_MODEL={model}")
        logger.info(f"   GOOGLE_CLOUD_LOCATION={region}")
    else:
        logger.info(f"\n❌ No working combinations found in priority tests")
        logger.info(f"   You may need to check Google Cloud Console for available models")

if __name__ == "__main__":
    asyncio.run(main())