"""Twilio voice webhook endpoint for handling incoming calls."""

import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.request_validator import RequestValidator
from app.config import settings
from app.core.models import TwilioWebhookRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Twilio request validator for webhook security
try:
    if not settings.twilio_auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set - signature validation will fail")
        request_validator = None
    else:
        request_validator = RequestValidator(settings.twilio_auth_token)
        logger.info("Twilio RequestValidator initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Twilio RequestValidator: {e}")
    request_validator = None


def validate_twilio_request(request: Request, body: str) -> bool:
    """Validate that the request is actually from Twilio.
    
    Args:
        request: FastAPI request object
        body: Raw request body as string
        
    Returns:
        True if request is valid, False otherwise
    """
    try:
        logger.info(f"Starting Twilio request validation")
        logger.info(f"Request validator available: {request_validator is not None}")
        
        # Check if request_validator is available
        if request_validator is None:
            logger.info("RequestValidator not initialized - skipping validation")
            return False
            
        # Get the X-Twilio-Signature header
        signature = request.headers.get('X-Twilio-Signature', '')
        logger.info(f"Twilio signature header present: {bool(signature)}")
        
        # Get the full URL
        url = str(request.url)
        logger.info(f"Request URL: {url}")
        logger.info(f"Request body type: {type(body)}")
        logger.info(f"Request body length: {len(body) if body else 0}")
        
        # Validate the request
        logger.info("Calling request_validator.validate()")
        is_valid = request_validator.validate(url, body, signature)
        logger.info(f"Validation result: {is_valid}")
        return is_valid
    except Exception as e:
        logger.error(f"Error validating Twilio request: {e}")
        logger.info(f"Request validator type: {type(request_validator)}")
        logger.info(f"Body type: {type(body)}")
        logger.info(f"URL type: {type(url)}")
        logger.info(f"Signature type: {type(signature)}")
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
        logger.info("=== Starting webhook handler ===")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Get raw body for signature validation
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Raw body received: {body_str}")
        
        # Validate request is from Twilio (optional but recommended)
        if settings.twilio_validate_signature:
            logger.info("About to validate Twilio request")
            if not validate_twilio_request(request, body_str):
                logger.warning("Invalid Twilio signature detected")
                # In production, you might want to reject invalid requests
                # raise HTTPException(status_code=403, detail="Invalid signature")
        else:
            logger.info("Twilio signature validation disabled")
        
        # Parse form data
        logger.info("About to parse form data")
        form_data = await request.form()
        logger.info(f"Form data parsed successfully: {dict(form_data)}")
        
        # Extract call information
        call_sid = form_data.get('CallSid')
        from_number = form_data.get('From')
        to_number = form_data.get('To')
        call_status = form_data.get('CallStatus')
        
        logger.info(f"Incoming call: {call_sid} from {from_number} to {to_number} (status: {call_status})")
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Add a brief greeting
        response.say("Hello!", voice='alice')
        
        # Start media stream to our WebSocket endpoint
        # The WebSocket URL should be accessible from Twilio's servers
        logger.info(f"Initial request.url.hostname: {request.url.hostname}, request.url.port: {request.url.port}")
        websocket_url = f"wss://{request.url.hostname}:{request.url.port}/ws/media-stream"
        logger.info(f"Intermediate websocket_url (before settings check): {websocket_url}")
        logger.info(f"Value of settings.twilio_webhook_url: {settings.twilio_webhook_url}")
        if settings.twilio_webhook_url:
            # Use configured webhook URL if available
            logger.info(f"Using settings.twilio_webhook_url to construct websocket_url.")
            websocket_url = settings.twilio_webhook_url.replace('http', 'ws') + "/ws/media-stream"
        else:
            logger.info(f"settings.twilio_webhook_url is not set. Using URL derived from request.")
            # Ensure port is handled correctly for standard https (port 443)
            port_str = f":{request.url.port}" if request.url.port else ""
            websocket_url = f"wss://{request.url.hostname}{port_str}/ws/media-stream"
        
        start = response.start()
        start.stream(
            url=websocket_url,
            track='both_tracks'  # Capture both inbound and outbound audio
        )
        
        logger.info(f"Generated TwiML for call {call_sid} with WebSocket URL: {websocket_url}")
        
        # Keep the call alive
        response.pause(length=60)  # Pause for 60 seconds to keep call active
        

        
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