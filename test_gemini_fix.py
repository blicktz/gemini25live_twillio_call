#!/usr/bin/env python3
"""
Test script to verify the Gemini Live API authentication fix.
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

async def test_gemini_client_initialization():
    """Test that the Gemini client can initialize with Vertex AI authentication."""
    try:
        logger.info("Testing Gemini client initialization with Vertex AI...")
        
        # Import after setting up the path
        from app.gemini_integration.streaming import GeminiStreamingClient
        
        # Try to initialize the client
        client = GeminiStreamingClient()
        logger.info("✅ Gemini client initialized successfully!")
        
        # Test that the client has the expected properties
        assert client.client is not None, "Client should not be None"
        assert hasattr(client.client, 'aio'), "Client should have aio attribute for async operations"
        assert hasattr(client.client.aio, 'live'), "Client should have live API access"
        
        logger.info("✅ Client has expected attributes for Live API")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini client: {e}")
        logger.exception("Full traceback:")
        return False

async def main():
    """Run the test."""
    logger.info("🚀 Starting Gemini Live API authentication test")
    
    # Check environment variables
    required_vars = [
        'GOOGLE_APPLICATION_CREDENTIALS',
        'GOOGLE_CLOUD_PROJECT', 
        'GOOGLE_CLOUD_LOCATION'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        return False
    
    logger.info("✅ All required environment variables are set")
    
    # Test client initialization
    success = await test_gemini_client_initialization()
    
    if success:
        logger.info("🎉 Authentication fix verified! Gemini Live API client can now initialize properly.")
        return True
    else:
        logger.error("💥 Authentication fix failed. Please check the configuration.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)