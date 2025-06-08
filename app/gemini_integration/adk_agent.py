"""
ADK Agent implementation for Twilio voice calls.
This is a minimal placeholder for Phase 1 of the refactoring.
Updated to use Vertex AI authentication.
"""

import logging
import os
from google.adk.agents import Agent
from app.config import settings

logger = logging.getLogger(__name__)

# Set up Vertex AI authentication environment variables
def setup_vertexai_auth():
    """Configure environment variables for Vertex AI authentication."""
    # Set the required environment variables for Vertex AI
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
    os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_location
    
    # Force Google GenAI to use Vertex AI
    if settings.google_genai_use_vertexai:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    
    logger.info(f"Vertex AI authentication configured:")
    logger.info(f"  Project: {settings.google_cloud_project}")
    logger.info(f"  Location: {settings.google_cloud_location}")
    logger.info(f"  Credentials: {settings.google_application_credentials}")
    logger.info(f"  Use Vertex AI: {settings.google_genai_use_vertexai}")

# Setup authentication before creating the agent
setup_vertexai_auth()

# Create the root agent with system instruction and Vertex AI configuration
root_agent = Agent(
    name="twilio_voice_assistant",
    model=settings.gemini_model,
    description="AI assistant for Twilio voice calls using Google ADK with Vertex AI.",
    instruction=settings.system_prompt
)

logger.info(f"ADK Agent created with model: {settings.gemini_model}")