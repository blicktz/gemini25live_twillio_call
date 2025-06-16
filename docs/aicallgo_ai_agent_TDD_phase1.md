# Technical Design Document (TDD) - AICallGO AI Agent Backend

## 1. Overview & Executive Summary

The AICallGO AI Agent backend is a specialized voice assistant system that integrates Twilio for telephony and Google's Gemini AI for natural language processing and voice synthesis. This system handles real-time phone conversations, processes audio streams bidirectionally, and leverages Google's ADK (Agent Development Kit) for conversational AI capabilities.

**Core Problem Solved**: The AI Agent backend enables businesses to automate phone interactions with customers using a natural-sounding AI voice assistant that can understand context, respond appropriately, and maintain conversation flow.

**Key Architectural Decisions**:
- **Twilio Integration**: Chosen for reliable telephony infrastructure and WebSocket-based media streaming
- **Google Gemini AI**: Selected for advanced conversational capabilities and high-quality voice synthesis
- **FastAPI Framework**: Used for its asynchronous capabilities, essential for real-time audio processing
- **Decoupled Architecture**: Separation between AI Agent and Web Backend via secure internal API
- **Stateful Session Management**: Maintaining call state for continuous conversation

## 2. Technology Stack Selection

- **Language/Framework**: Python 3.12 with FastAPI for asynchronous request handling and WebSocket support, critical for real-time audio streaming.
- **AI Model**: Google Gemini via Vertex AI, chosen for its superior conversational abilities and voice synthesis quality.
- **Telephony**: Twilio Voice API with Media Streams for bidirectional audio communication.
- **Audio Processing**: Python's `audioop` library for efficient audio format conversion and resampling.
- **Authentication**: Environment-based API key authentication for Vertex AI and signature validation for Twilio webhooks.
- **State Management**: In-memory session tracking with Redis integration capability for distributed deployment.
- **Logging**: Structured logging with correlation IDs for call tracing and debugging.
- **Error Handling**: Circuit breaker pattern for external API calls with graceful degradation.
- **Internal API Client**: Async HTTP client for communication with Web Backend.

## 3. System Architecture & Component Design

```
┌─────────────────┐    ┌──────────────────────────────────────┐    ┌─────────────────┐
│                 │    │             AI Agent                  │    │                 │
│                 │    │                                      │    │                 │
│    Twilio       │    │  ┌─────────────┐  ┌─────────────┐   │    │  Google Vertex  │
│    Voice        │◄───┤►│ Twilio      │  │ Gemini      │   │◄───┤►│  AI            │
│    Platform     │    │  │ Integration │  │ Integration │   │    │  │ (Gemini)     │
│                 │    │  └─────────────┘  └─────────────┘   │    │                 │
└─────────────────┘    │         │              │            │    └─────────────────┘
                       │         │              │            │
                       │         ▼              ▼            │
                       │  ┌─────────────────────────────┐    │
                       │  │                             │    │    ┌─────────────────┐
                       │  │      Audio Processing       │    │    │                 │
                       │  │                             │    │    │  Web Backend    │
                       │  └─────────────────────────────┘    │◄───┤►│  (FastAPI)     │
                       │                │                     │    │                 │
                       │                ▼                     │    └─────────────────┘
                       │  ┌─────────────────────────────┐    │
                       │  │                             │    │
                       │  │      Call Session Mgmt      │    │
                       │  │                             │    │
                       │  └─────────────────────────────┘    │
                       │                                      │
                       └──────────────────────────────────────┘
```

**Component Breakdown**:

- **Twilio Integration**: Handles incoming call webhooks, WebSocket connections for media streams, and audio delivery back to the caller.
  - **Webhooks Module**: Processes incoming call notifications and generates TwiML responses.
  - **WebSockets Module**: Manages real-time bidirectional audio streaming with Twilio.

- **Gemini Integration**: Interfaces with Google's Vertex AI platform to access Gemini's conversational capabilities.
  - **ADK Agent**: Configures and manages the Gemini agent with system instructions.
  - **Streaming Client**: Handles real-time audio/text streaming to and from Gemini.

- **Audio Processing**: Converts audio between formats required by Twilio (8kHz μ-law) and Gemini (24kHz PCM).
  - **Format Conversion**: Transforms between μ-law and PCM formats.
  - **Resampling**: Adjusts sample rates between systems.
  - **Encoding/Decoding**: Handles base64 encoding/decoding for transmission.

- **Call Session Management**: Maintains state for active calls and coordinates between components.
  - **Session Tracking**: Keeps track of active call sessions and their metadata.
  - **Event Coordination**: Manages the flow of events between Twilio and Gemini.

- **Web Backend Integration**: Communicates with the Web Backend to retrieve business configurations and store call logs.
  - **API Client**: Makes authenticated requests to the internal API.
  - **Resilience Patterns**: Implements retry logic and circuit breaker for API calls.

## 4. Data Structure Design

### Application-Layer Data Models

```python
from pydantic import BaseModel
from typing import Dict, Optional, Any, List, Union
from datetime import datetime

# Twilio webhook request model
class TwilioWebhookRequest(BaseModel):
    CallSid: str
    From: str
    To: str
    CallStatus: str
    Direction: Optional[str] = None
    ForwardedFrom: Optional[str] = None
    CallerName: Optional[str] = None
    ParentCallSid: Optional[str] = None
    AccountSid: Optional[str] = None

# Twilio media message model
class TwilioMediaMessage(BaseModel):
    event: str
    streamSid: Optional[str] = None
    start: Optional[Dict[str, Any]] = None
    media: Optional[Dict[str, Any]] = None
    stop: Optional[Dict[str, Any]] = None
    mark: Optional[Union[Dict[str, Any], Any]] = None

# Twilio outbound media model
class TwilioOutboundMedia(BaseModel):
    payload: str  # Base64 encoded audio
    track: str = "inbound_track"  # Default to inbound track

# Audio chunk model
class AudioChunk(BaseModel):
    audio_data: bytes
    sample_rate: int
    format: str  # "mulaw" or "pcm"
    timestamp: float

# Call session model
class CallSession(BaseModel):
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    business_id: Optional[int] = None
    is_active: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    transcript: List[Dict[str, Any]] = []
    ai_responses: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}

# Business configuration model (from Web Backend)
class BusinessConfig(BaseModel):
    business_id: int
    name: str
    system_prompt: str
    voice_settings: Optional[Dict[str, Any]] = None
    response_style: Optional[str] = "professional"
    max_call_duration: int = 300
    is_active: bool = True

# Call log model (for Web Backend API)
class CallLogCreate(BaseModel):
    business_id: int
    call_sid: str
    caller_phone: Optional[str] = None
    call_duration: Optional[int] = None
    call_status: str
    transcript: Optional[str] = None
    ai_responses: Optional[Dict[str, Any]] = None
    call_metadata: Optional[Dict[str, Any]] = None
```

## 5. API Endpoint Design (RESTful Contract)

### External Endpoints (Public)

| HTTP Method | Endpoint Path | Description | Authentication |
|-------------|---------------|-------------|----------------|
| POST | `/twilio-voice` | Twilio voice webhook for incoming calls | Twilio Signature Validation |
| POST | `/twilio-status` | Twilio call status updates | Twilio Signature Validation |
| WebSocket | `/media-stream` | WebSocket endpoint for Twilio media streams | None (Twilio-initiated) |
| GET | `/health` | Health check endpoint | None |

### Internal API Client (for Web Backend Communication)

| HTTP Method | Endpoint Path | Description | Authentication |
|-------------|---------------|-------------|----------------|
| GET | `/internal/businesses/verify-number/{phone_number}` | Verify if a phone number belongs to a registered business | API Key |
| GET | `/internal/businesses/{business_id}/remaining-minutes` | Check remaining call minutes for a business | API Key |
| GET | `/internal/businesses/{business_id}/config` | Get business configuration | API Key |
| POST | `/internal/call-logs` | Create call log entry | API Key |
| PUT | `/internal/call-logs/{call_sid}` | Update call log | API Key |

## 6. Implementation Guidelines & Best Practices

### Project Structure

```
app/
├── __init__.py
├── main.py                 # FastAPI app initialization
├── config.py              # Settings and environment variables
├── audio_processing/
│   ├── __init__.py
│   └── utils.py           # Audio conversion utilities
├── core/
│   ├── __init__.py
│   └── models.py          # Pydantic data models
├── gemini_integration/
│   ├── __init__.py
│   ├── adk_agent.py       # Gemini ADK agent setup
│   └── streaming.py       # Streaming client for Gemini
├── twilio_integration/
│   ├── __init__.py
│   ├── webhooks.py        # Twilio webhook handlers
│   └── websockets.py      # WebSocket handler for media streams
├── web_backend/
│   ├── __init__.py
│   ├── client.py          # API client for Web Backend
│   └── models.py          # Models for Web Backend API
└── utils/
    ├── __init__.py
    ├── logging.py         # Logging configuration
    └── resilience.py      # Retry and circuit breaker patterns
```

### Configuration Management

```python
# config.py
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, Literal

class Settings(BaseSettings):
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_webhook_url: Optional[str] = None
    twilio_validate_signature: bool = True
    
    # Google Cloud/Vertex AI Configuration
    google_cloud_credentials: Optional[str] = None
    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    use_vertex_ai: bool = True
    
    # Gemini Live API Configuration
    gemini_model_name: str = "gemini-1.5-flash"
    gemini_api_version: str = "v1"
    gemini_language_code: str = "en-US"
    gemini_voice_name: Optional[str] = None
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Audio Configuration
    input_sample_rate: int = 8000  # Twilio sends 8kHz
    output_sample_rate: int = 8000  # Twilio expects 8kHz
    gemini_input_sample_rate: int = 24000  # Gemini expects 24kHz
    gemini_output_sample_rate: int = 24000  # Gemini sends 24kHz
    save_debug_audio: bool = False
    
    # Twilio Audio Delivery
    use_twilio_audio_queue: bool = True
    
    # AI Configuration
    system_prompt: str = "You are a helpful AI assistant..."
    
    # Web Backend Integration
    web_backend_base_url: str
    web_backend_api_key: str
    web_backend_timeout: int = 10  # Timeout in seconds
    web_backend_verify_ssl: bool = True
    
    # Call Transcript Settings
    save_call_transcripts: bool = True
    transcript_format: Literal["json", "text"] = "json"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Testing Strategy

- **Unit Tests**: Test individual components in isolation
  - Audio processing utilities
  - Data model validation
  - Configuration loading

- **Integration Tests**: Test interaction between components
  - Twilio webhook handling
  - WebSocket communication
  - Gemini API integration

- **Mock Tests**: Use mocks for external dependencies
  - Mock Twilio media streams
  - Mock Gemini responses
  - Mock Web Backend API

- **End-to-End Tests**: Test complete call flow
  - Simulated call with audio input/output
  - Verification of call logs

- **Performance Tests**: Measure system under load
  - Audio processing latency
  - Concurrent call handling

### Logging Strategy

```python
# Structured logging with correlation IDs
import logging
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        # Add call correlation IDs when available
        if hasattr(record, 'call_sid'):
            log_entry['call_sid'] = record.call_sid
        if hasattr(record, 'stream_sid'):
            log_entry['stream_sid'] = record.stream_sid
        if hasattr(record, 'business_id'):
            log_entry['business_id'] = record.business_id
            
        return json.dumps(log_entry)
```

### Deployment

**Docker Configuration**:

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Deployment Considerations**:

- **Scaling**: Horizontal scaling for handling multiple concurrent calls
- **Resource Requirements**: Minimum 2 CPU cores and 4GB RAM per instance
- **Network**: Low-latency connection to Twilio and Google Vertex AI
- **Security**: Firewall rules to allow only Twilio webhook IPs
- **Monitoring**: CPU, memory, and network usage metrics
- **Alerting**: Notification for high error rates or latency

### Web Backend Integration

```python
# web_backend/client.py
import httpx
import logging
from app.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pybreaker import CircuitBreaker
from app.core.models import BusinessConfig, CallLogCreate
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class WebBackendClient:
    def __init__(self):
        self.base_url = settings.web_backend_base_url
        self.api_key = settings.web_backend_api_key
        self.headers = {"X-API-Key": self.api_key}
        self.timeout = settings.web_backend_timeout
        self.verify_ssl = settings.web_backend_verify_ssl
        self.circuit_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the Web Backend API with error handling"""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("headers", self.headers)
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify_ssl)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await self.circuit_breaker.call_async(
                    getattr(client, method),
                    url,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)))
    async def verify_business_number(self, to_number: str) -> Dict[str, Any]:
        """Verify if a phone number belongs to a registered business"""
        return await self._make_request(
            "get",
            f"/internal/businesses/verify-number/{to_number}"
        )
    
    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)))
    async def check_remaining_minutes(self, business_id: int) -> Dict[str, Any]:
        """Check remaining call minutes for a business"""
        return await self._make_request(
            "get",
            f"/internal/businesses/{business_id}/remaining-minutes"
        )
    
    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)))
    async def get_business_config(self, business_id: int) -> BusinessConfig:
        """Get business configuration from Web Backend"""
        data = await self._make_request(
            "get",
            f"/internal/businesses/{business_id}/config"
        )
        return BusinessConfig(**data)
    
    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)))
    async def create_call_log(self, call_log: CallLogCreate) -> Dict[str, Any]:
        """Create call log entry in Web Backend"""
        return await self._make_request(
            "post",
            "/internal/call-logs",
            json=call_log.dict(exclude_none=True)
        )
    
    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)))
    async def update_call_log(self, call_sid: str, call_log_data: dict) -> Dict[str, Any]:
        """Update call log entry in Web Backend"""
        return await self._make_request(
            "put",
            f"/internal/call-logs/{call_sid}",
            json=call_log_data
        )
```

### Error Handling

- **Graceful Degradation**: Fallback to default responses if Gemini API is unavailable
- **Retry Logic**: Exponential backoff for transient failures
- **Circuit Breaker**: Prevent cascading failures from external dependencies
- **Comprehensive Logging**: Detailed error information for debugging
- **User-Friendly Responses**: Polite error messages for callers when issues occur

### Call Transcript Handling

- **Transcript Collection**: Capture both user speech and AI responses during the call
- **Storage Format**: Store transcripts in JSON format with timestamps, speaker identification, and text content
- **Real-time Processing**: Update transcript data during the call for immediate access
- **End of Call Processing**: Finalize and save complete transcript when call ends
- **Web Backend Integration**: Send transcript data to Web Backend for storage and analysis
- **Privacy Considerations**: Implement data retention policies and ensure compliance with privacy regulations

```python
# Example transcript JSON structure
{
    "call_sid": "CA123456789abcdef",
    "business_id": 42,
    "start_time": "2023-06-15T14:30:45.123Z",
    "end_time": "2023-06-15T14:35:12.456Z",
    "transcript": [
        {
            "timestamp": "2023-06-15T14:30:48.789Z",
            "speaker": "ai",
            "text": "Hello, thank you for calling. How can I help you today?"
        },
        {
            "timestamp": "2023-06-15T14:31:02.123Z",
            "speaker": "user",
            "text": "I'd like to check my account balance please."
        },
        {
            "timestamp": "2023-06-15T14:31:08.456Z",
            "speaker": "ai",
            "text": "I'd be happy to help you check your account balance. Could you please verify your identity by providing your account number?"
        }
    ]
}
```

### Security Best Practices

- **API Key Management**: Secure storage of API keys in environment variables
- **Signature Validation**: Verify Twilio webhook signatures
- **Input Validation**: Validate all incoming data with Pydantic models
- **Secure Headers**: Set appropriate security headers for HTTP responses
- **Rate Limiting**: Protect endpoints from abuse
- **Audit Logging**: Log all security-relevant events

