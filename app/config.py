"""Configuration module for loading environment variables."""

import os
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_webhook_url: Optional[str] = None
    
    # Gemini API Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash-preview"
    
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()