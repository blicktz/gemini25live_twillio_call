"""
ADK Agent implementation for Twilio voice calls.
This is a minimal placeholder for Phase 1 of the refactoring.
"""

import logging
from google.adk.agents import Agent
from app.config import settings

logger = logging.getLogger(__name__)

# Create the root agent with system instruction
root_agent = Agent(
    name="twilio_voice_assistant",
    model=settings.gemini_model,
    description="AI assistant for Twilio voice calls using Google ADK.",
    instruction=settings.system_prompt
)