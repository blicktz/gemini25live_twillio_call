#!/usr/bin/env python3
"""
Test Gemini Live API using direct Google AI API instead of Vertex AI
"""
import asyncio
import logging
import os
from google import genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_direct_api():
    """Test using Google AI API directly instead of Vertex AI"""
    
    # Check if we have an API key in environment
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.error("❌ GEMINI_API_KEY not found in environment")
        logger.info("   You can get an API key from: https://aistudio.google.com/app/apikey")
        return False
    
    try:
        logger.info("🧪 Testing direct Google AI API (not Vertex AI)")
        
        # Configure the client for direct API
        client = genai.Client(api_key=api_key)
        
        # Test available models
        logger.info("📋 Checking available models...")
        models = client.models.list()
        
        live_models = []
        for model in models:
            if hasattr(model, 'supported_generation_methods'):
                if 'generateContent' in model.supported_generation_methods:
                    logger.info(f"   📝 Text model: {model.name}")
                # Check for live/streaming capabilities
                if any('live' in method.lower() or 'stream' in method.lower() 
                       for method in model.supported_generation_methods):
                    live_models.append(model.name)
                    logger.info(f"   🎙️  Live model: {model.name}")
        
        if live_models:
            logger.info(f"✅ Found {len(live_models)} Live API compatible models")
            return True
        else:
            logger.info("❌ No Live API compatible models found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing direct API: {e}")
        return False

async def test_vertex_ai_regions():
    """Test different Vertex AI regions"""
    regions_to_test = [
        "us-central1",
        "us-east1", 
        "us-west1",
        "europe-west1",
        "asia-southeast1"
    ]
    
    logger.info("🌍 Testing Vertex AI regions for Live API availability...")
    
    for region in regions_to_test:
        try:
            logger.info(f"   Testing region: {region}")
            
            # Try to create a client for this region
            client = genai.Client(
                vertexai=True,
                project="twilio-gemini25-live-api",
                location=region
            )
            
            # Try to list models (this will fail if region doesn't support the API)
            # Note: This might still fail due to billing/permissions, but different error
            logger.info(f"   ✅ {region}: Client created successfully")
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                logger.info(f"   ❌ {region}: Live API not available (404)")
            elif "billing" in error_msg.lower():
                logger.info(f"   ⚠️  {region}: Billing issue")
            else:
                logger.info(f"   ❌ {region}: {error_msg}")

async def main():
    logger.info("🔍 Comprehensive Gemini Live API Diagnosis")
    logger.info("=" * 50)
    
    logger.info("\n1. Testing Direct Google AI API...")
    direct_api_works = await test_direct_api()
    
    logger.info("\n2. Testing Vertex AI Regions...")
    await test_vertex_ai_regions()
    
    logger.info("\n" + "=" * 50)
    logger.info("📋 DIAGNOSIS SUMMARY:")
    
    if direct_api_works:
        logger.info("✅ Direct Google AI API is available")
        logger.info("💡 RECOMMENDATION: Use Google AI API instead of Vertex AI")
        logger.info("   Set GEMINI_API_KEY in your .env file")
        logger.info("   Get API key from: https://aistudio.google.com/app/apikey")
    else:
        logger.info("❌ Direct Google AI API not available or no API key")
    
    logger.info("\n🔗 Additional Resources:")
    logger.info("   - Gemini Live API docs: https://ai.google.dev/gemini-api/docs/live-api")
    logger.info("   - Vertex AI Live API: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/live-api")
    logger.info("   - API Key: https://aistudio.google.com/app/apikey")

if __name__ == "__main__":
    asyncio.run(main())