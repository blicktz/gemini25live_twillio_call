import logging
from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
from twilio.request_validator import RequestValidator # For request validation

from app.config import settings # To get BASE_URL and TWILIO_AUTH_TOKEN

# Configure basic logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Ensure basicConfig is set if not already by root logger
    logging.basicConfig(level=settings.LOG_LEVEL.upper() if settings.LOG_LEVEL else logging.INFO)

router = APIRouter()

def _get_websocket_url() -> str:
    """
    Constructs the WebSocket URL for the media stream from BASE_URL.
    Ensures it uses wss:// scheme.
    """
    base_url = settings.BASE_URL
    if not base_url:
        logger.error("BASE_URL is not configured. Cannot create WebSocket URL.")
        raise ValueError("BASE_URL is not configured.")

    # Remove http:// or https:// scheme if present
    if base_url.startswith("http://"):
        base_url_no_scheme = base_url[len("http://"):]
    elif base_url.startswith("https://"):
        base_url_no_scheme = base_url[len("https://"):]
    else:
        base_url_no_scheme = base_url

    # Remove trailing slashes if any
    base_url_no_scheme = base_url_no_scheme.rstrip('/')

    ws_url = f"wss://{base_url_no_scheme}/ws/media-stream"
    logger.info(f"Constructed WebSocket URL: {ws_url}")
    return ws_url

@router.post("/twilio-voice", response_class=Response)
async def twilio_voice_webhook(request: Request):
    """
    Handles incoming Twilio voice calls.
    Generates TwiML to start a bi-directional media stream to the WebSocket endpoint.
    Includes optional request validation.
    """
    logger.info(f"Received Twilio voice webhook request: {request.url}")

    # 1. Twilio Request Validation (Optional but Recommended for Production)
    # The twilio-python library's RequestValidator uses the TWILIO_AUTH_TOKEN.
    # If TWILIO_REQUEST_VALIDATION_SECRET is different and intended for primary webhook validation,
    # a custom HMAC-SHA1 validation implementation would be needed instead of RequestValidator.
    # For this MVP, we rely on RequestValidator with TWILIO_AUTH_TOKEN as is standard.
    if settings.TWILIO_AUTH_TOKEN and "X-Twilio-Signature" in request.headers:
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        url = str(request.url)

        # For FastAPI, request.form() needs to be awaited and returns an immutable starlette FormData
        # which is compatible with what Twilio's validator expects (a dict-like object).
        try:
            post_vars = await request.form()
            # Convert to dict for validator if it's strict, though FormData often works.
            post_vars_dict = dict(post_vars.items())
        except Exception as e:
            logger.error(f"Error reading form data for validation: {e}")
            # If form data cannot be read, validation cannot proceed.
            # Depending on security policy, either deny or proceed with caution.
            # For this example, we'll log and attempt to proceed, but in prod, might deny.
            post_vars_dict = {}


        signature = request.headers.get("X-Twilio-Signature")

        if not validator.validate(url, post_vars_dict, signature):
            logger.warning(f"Twilio request validation failed for URL: {url}. Signature: {signature}")
            return Response(content="Invalid Twilio Signature. Access Denied.", status_code=403, media_type="text/plain")
        logger.info("Twilio request validation successful.")
    elif settings.TWILIO_AUTH_TOKEN:
        # If auth token is configured but signature is missing, it's suspicious.
        logger.warning("X-Twilio-Signature header missing, but TWILIO_AUTH_TOKEN is configured. Skipping validation (unsafe for production).")
    else:
        logger.info("TWILIO_AUTH_TOKEN not configured. Skipping Twilio request validation (unsafe for production).")

    # 2. Generate TwiML Response
    response = VoiceResponse()

    try:
        websocket_url = _get_websocket_url()

        # Say a message to the caller before starting the stream
        response.say(
            "Thank you for calling. We are connecting you to our AI voice assistant. Please wait a moment.",
            voice="Polly.Joanna-Neural" # Example of a more natural voice
        )

        # Start the media stream
        start = Start()
        start.stream(url=websocket_url)
        response.append(start)

        # Add a pause and a follow-up message in case the stream fails to connect or ends prematurely.
        # This part of TwiML executes if the <Stream> completes or fails to initiate properly
        # and Twilio moves to the next verb.
        response.pause(length=1) # Give a brief moment for the stream to attempt connection.
        response.say(
            "We seem to be having trouble connecting you to our AI services right now. "
            "Please hang up and try your call again later.",
            voice="Polly.Joanna-Neural"
        )
        response.hangup()

        twiml_output = str(response)
        logger.info(f"Generated TwiML response: {twiml_output}")
        return Response(content=twiml_output, media_type="application/xml")

    except ValueError as e: # Catch specific error from _get_websocket_url if BASE_URL is missing
        logger.error(f"Configuration error: {e}")
        # Fallback TwiML if critical config like BASE_URL is missing
        response = VoiceResponse()
        response.say("We are sorry, but the service is currently misconfigured. Please try again later.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml", status_code=500)
    except Exception as e:
        logger.exception("An unexpected error occurred while generating TwiML response.")
        # Generic error TwiML
        response = VoiceResponse()
        response.say("An unexpected error occurred. Please try your call again later.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml", status_code=500)

# This router would be included in the main FastAPI application.
# Example in main.py:
# from app.twilio_integration import webhooks as twilio_webhooks_router
# app.include_router(twilio_webhooks_router.router, prefix="/api/v1/twilio") # Or similar prefix
