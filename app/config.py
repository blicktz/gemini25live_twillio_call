"""Configuration module for loading environment variables."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_webhook_url: Optional[str] = None
    twilio_validate_signature: bool = True
    
    # Google Cloud / Vertex AI Configuration
    google_application_credentials: str
    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    
    # Gemini Live API Configuration (via Vertex AI)
    gemini_model: str = "gemini-2.0-flash-live-preview-04-09"
    gemini_api_version: str = "v1alpha" # For Live API
    gemini_language_code: str = "en-US" # For native audio dialog
    gemini_voice_name: Optional[str] = None # e.g., "Puck", if we want to specify a voice
    
    # Legacy API Key (keeping for reference, but not used with Vertex AI)
    # gemini_api_key: Optional[str] = None
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Audio Configuration
    input_sample_rate: int = 8000  # Twilio input sample rate
    gemini_input_sample_rate: int = 16000  # Gemini expected input
    gemini_output_sample_rate: int = 24000  # Gemini output sample rate
    output_sample_rate: int = 8000  # Twilio output sample rate
    
    # AI Configuration
    system_prompt: str = "You are a friendly and helpful AI assistant answering phone calls. Keep your responses conversational, concise, and natural. Respond as if you're having a real-time voice conversation."
    
    # Logging Configuration (Example - Add if not present and used by Gemini client)
    LOG_LEVEL: str = "INFO"


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()