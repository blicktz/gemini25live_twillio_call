"""Pydantic models for request/response structures."""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class TwilioWebhookRequest(BaseModel):
    """Model for Twilio voice webhook request."""
    CallSid: str
    From: str
    To: str
    CallStatus: str
    Direction: str
    AccountSid: str
    

class TwilioMediaMessage(BaseModel):
    """Model for Twilio media stream messages."""
    event: str
    sequenceNumber: Optional[str] = None
    media: Optional[Dict[str, Any]] = None
    start: Optional[Dict[str, Any]] = None
    stop: Optional[Dict[str, Any]] = None


class TwilioOutboundMedia(BaseModel):
    """Model for outbound media messages to Twilio."""
    event: str = "media"
    streamSid: str
    media: Dict[str, str]  # Contains 'payload' with base64 encoded audio


class AudioChunk(BaseModel):
    """Model for audio data chunks."""
    data: bytes
    sample_rate: int
    timestamp: float
    sequence_number: Optional[int] = None


class CallSession(BaseModel):
    """Model for tracking call session state."""
    call_sid: str
    stream_sid: Optional[str] = None
    is_active: bool = True
    gemini_session_id: Optional[str] = None