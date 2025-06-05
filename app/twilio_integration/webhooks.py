"""Twilio voice webhook endpoint for handling incoming calls."""

import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from twilio.twiml import VoiceResponse
from twilio.request_validator import RequestValidator
from app.config import settings
from app.core.models import TwilioWebhookRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Twilio request validator for webhook security
request_validator = RequestValidator(settings.twilio_auth_token)


def validate_twilio_request(request: Request, body: str) -> bool:
    """Validate that the request is actually from Twilio.
    
    Args:
        request: FastAPI request object
        body: Raw request body as string
        
    Returns:
        True if request is valid, False otherwise
    """
    try:
        # Get the X-Twilio-Signature header
        signature = request.headers.get('X-Twilio-Signature', '')
        
        # Get the full URL
        url = str(request.url)
        
        # Validate the request
        return request_validator.validate(url, body, signature)
    except Exception as e:
        logger.error(f"Error validating Twilio request: {e}")
        return False


@router.post("/twilio-voice")
async def handle_incoming_call(request: Request):
    """Handle incoming Twilio voice webhook.
    
    This endpoint receives incoming call notifications from Twilio and
    generates TwiML to start a media stream to our WebSocket endpoint.
    
    Returns:
        TwiML response to start media streaming
    """
    try:
        # Get raw body for signature validation
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Validate request is from Twilio (optional but recommended)
        if not validate_twilio_request(request, body_str):
            logger.warning("Invalid Twilio signature detected")
            # In production, you might want to reject invalid requests
            # raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parse form data
        form_data = await request.form()
        
        # Extract call information
        call_sid = form_data.get('CallSid')
        from_number = form_data.get('From')
        to_number = form_data.get('To')
        call_status = form_data.get('CallStatus')
        
        logger.info(f"Incoming call: {call_sid} from {from_number} to {to_number} (status: {call_status})")
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Add a brief greeting
        response.say("Hello! Please wait while I connect you to our AI assistant.", voice='alice')
        
        # Start media stream to our WebSocket endpoint
        # The WebSocket URL should be accessible from Twilio's servers
        websocket_url = f"wss://{request.url.hostname}:{request.url.port}/ws/media-stream"
        if settings.twilio_webhook_url:
            # Use configured webhook URL if available
            websocket_url = settings.twilio_webhook_url.replace('http', 'ws') + "/ws/media-stream"
        
        start = response.start()
        start.stream(
            url=websocket_url,
            track='both_tracks'  # Capture both inbound and outbound audio
        )
        
        # Keep the call alive
        response.pause(length=60)  # Pause for 60 seconds to keep call active
        
        logger.info(f"Generated TwiML for call {call_sid} with WebSocket URL: {websocket_url}")
        
        # Return TwiML response
        return Response(
            content=str(response),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}")
        
        # Return error TwiML
        error_response = VoiceResponse()
        error_response.say("Sorry, there was an error processing your call. Please try again later.")
        error_response.hangup()
        
        return Response(
            content=str(error_response),
            media_type="application/xml"
        )


@router.post("/twilio-status")
async def handle_call_status(request: Request):
    """Handle call status updates from Twilio.
    
    This endpoint receives status updates about calls (e.g., completed, failed).
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        call_status = form_data.get('CallStatus')
        
        logger.info(f"Call status update: {call_sid} - {call_status}")
        
        # Log call completion
        if call_status in ['completed', 'failed', 'busy', 'no-answer']:
            logger.info(f"Call {call_sid} ended with status: {call_status}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling call status: {e}")
        return {"status": "error", "message": str(e)}