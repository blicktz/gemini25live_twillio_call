"""FastAPI app initialization and main entry point."""

import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.twilio_integration.webhooks import router as twilio_router
from app.twilio_integration.websockets import handle_media_stream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="AI Call Answering Service",
    description="FastAPI backend for AI-powered call answering using Twilio and Gemini API",
    version="1.0.0",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Twilio webhook routes
app.include_router(twilio_router, prefix="/api/v1", tags=["twilio"])


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "message": "AI Call Answering Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ai-call-answering",
        "timestamp": "2024-01-01T00:00:00Z"  # In production, use actual timestamp
    }


@app.websocket("/ws/media-stream")
async def websocket_media_stream(websocket: WebSocket):
    """WebSocket endpoint for Twilio media streams.
    
    This endpoint receives real-time audio data from Twilio and
    processes it through the Gemini API for AI responses.
    
    Args:
        websocket: WebSocket connection from Twilio
    """
    logger.info("New WebSocket connection for media stream")
    await handle_media_stream(websocket)


@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    logger.info("Starting AI Call Answering Service")
    logger.info(f"Configuration:")
    logger.info(f"  - Host: {settings.host}")
    logger.info(f"  - Port: {settings.port}")
    logger.info(f"  - Debug: {settings.debug}")
    logger.info(f"  - Gemini Model: {settings.gemini_model}")
    logger.info(f"  - Input Sample Rate: {settings.input_sample_rate}Hz")
    logger.info(f"  - Gemini Input Sample Rate: {settings.gemini_input_sample_rate}Hz")
    logger.info(f"  - Gemini Output Sample Rate: {settings.gemini_output_sample_rate}Hz")
    logger.info(f"  - Output Sample Rate: {settings.output_sample_rate}Hz")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    logger.info("Shutting down AI Call Answering Service")
    # Clean up any active sessions or resources here


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )