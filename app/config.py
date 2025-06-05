import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER")
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

    # Gemini API Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

    # Application Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    # For Twilio request validation
    TWILIO_REQUEST_VALIDATION_SECRET: str = os.getenv("TWILIO_REQUEST_VALIDATION_SECRET")


settings = Settings()

# Basic validation to ensure critical variables are set
if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
    raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env file or environment.")

if not settings.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY must be set in .env file or environment.")

if not settings.TWILIO_PHONE_NUMBER:
    print("Warning: TWILIO_PHONE_NUMBER is not set. This might be needed for some operations.")

print(f"Settings loaded. Base URL: {settings.BASE_URL}")
