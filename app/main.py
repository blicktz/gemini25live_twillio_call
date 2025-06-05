import logging
import sys
import uvicorn # For running the app directly

from fastapi import FastAPI

from app.config import settings
from app.twilio_integration.webhooks import router as twilio_webhooks_router
from app.twilio_integration.websockets import twilio_media_stream_ws_endpoint

# --- Logging Configuration ---
# Determine the log level from settings, defaulting to INFO if not specified or invalid
log_level_str = settings.LOG_LEVEL.upper() if settings.LOG_LEVEL else "INFO"
numeric_log_level = getattr(logging, log_level_str, logging.INFO)

# Configure basic logging to output to stdout
logging.basicConfig(
    stream=sys.stdout,
    level=numeric_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logger.info(f"Logging configured with level: {logging.getLevelName(numeric_log_level)}")

# --- FastAPI Application Initialization ---
app = FastAPI(
    title="AI Call Answering Service",
    description="A FastAPI application to handle Twilio voice calls with AI processing via Gemini.",
    version="0.1.0",
    # Other FastAPI parameters like docs_url, redoc_url can be set here
)

# --- Include Routers ---
# The Twilio webhook endpoint(s) will be available under the /api prefix
# e.g., {BASE_URL}/api/twilio-voice
app.include_router(twilio_webhooks_router, prefix="/api")
logger.info("Twilio webhooks router included with prefix /api.")

# --- Add WebSocket Endpoint ---
# The WebSocket endpoint for Twilio media streams
# This will be available at wss://{BASE_URL_HOST_PORT}/ws/media-stream
app.add_api_websocket_route("/ws/media-stream", twilio_media_stream_ws_endpoint)
logger.info("Twilio media stream WebSocket endpoint added at /ws/media-stream.")

# --- Root Endpoint (Health Check) ---
@app.get("/")
async def root():
    """
    Simple root endpoint for health checks or a basic welcome message.
    """
    logger.info("Root endpoint '/' accessed.")
    return {"message": "AI Call Answering Service is running."}

# --- Main Execution Block (for direct run) ---
if __name__ == "__main__":
    logger.info("Starting Uvicorn server directly for development...")
    # The port should ideally be configurable, e.g., from settings or environment variable
    # For now, using a common default of 8000.
    # Uvicorn's log_level can also be set from settings.
    uvicorn_log_level = settings.LOG_LEVEL.lower() if settings.LOG_LEVEL else "info"

    # Note: When running with `python app/main.py`, Uvicorn uses its own logging config
    # which might differ slightly from the basicConfig above unless further harmonized.
    # For production, you'd typically use `uvicorn app.main:app --host 0.0.0.0 --port 8000`
    uvicorn.run(
        "app.main:app", # Points to the 'app' instance in this file
        host="0.0.0.0",
        port=8000, # Consider making this configurable via settings.APP_PORT
        log_level=uvicorn_log_level,
        reload=True # Enable auto-reload for development; disable in production
    )
    # If you want the Python logging to be the primary, you might need to disable Uvicorn's access/default loggers
    # or use a custom logging class with Uvicorn. For MVP, this is usually fine.
```
