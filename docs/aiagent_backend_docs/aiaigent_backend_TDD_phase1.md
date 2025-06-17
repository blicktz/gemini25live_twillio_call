# AI Agent Backend - Technical Design Document (TDD) - Phase 1

**Document Version**: 1.1  
**Date**: June 2025
**Author**: AI Backend Architect

## 1. Overview & Executive Summary

This document outlines the technical design for the AI Agent backend service. The AI Agent is responsible for handling incoming calls via Twilio, interacting with users using Google Gemini 2.0 Live model via Google ADK, and communicating with the existing Web Backend for business logic and data retrieval. This TDD focuses on building a stateless, scalable, and secure FastAPI application deployed on Render.com, designed to integrate seamlessly with the Web Backend and Twilio services.

The core problem being solved is the automated handling of customer calls for Small and Medium-sized Businesses (SMBs) when owners are unavailable, providing a conversational AI experience.

**Key Architectural Decisions & Justifications:**

*   **FastAPI Framework:** Chosen for its high performance, asynchronous capabilities (crucial for real-time audio streaming and API calls), automatic data validation (Pydantic), and OpenAPI documentation generation, which aligns with the project's need for efficient development and clear API contracts.
*   **Stateless Design:** The AI Agent will not maintain its own database. All persistent data (business configurations, call logs, user information) will be managed by the existing Web Backend. This simplifies the AI Agent's architecture, enhances scalability, and centralizes data management.
*   **Google ADK with Gemini 2.0 Live:** Leveraged for advanced conversational AI capabilities, including real-time audio processing and natural language understanding, as specified in the requirements, with robust error handling and session recovery.
*   **Twilio Integration:** Used for all telephony interactions, including receiving incoming calls, streaming audio to/from the AI model, and managing call lifecycle (hang-ups, recordings).
*   **Render.com Deployment:** Selected for its ease of use for deploying containerized Python applications, managed services, and scalability options.
*   **Web Backend API Consumption:** The AI Agent will rely heavily on the Web Backend's APIs (as specified in `webbackend_api_update_specification.md`) for pre-call verification, fetching business/agent configurations, and posting call logs/recordings. This ensures a single source of truth for business data.
*   **Security via API Keys:** Service-to-service communication between the AI Agent and the Web Backend will be secured using API keys (`X-API-Key`), as already established in the Web Backend.
*   **Robust Error Handling:** Comprehensive error recovery strategies for Gemini ADK failures, Web Backend API timeouts, and audio processing issues.

## 2. Technology Stack Selection

*   **Language/Framework:** Python 3.12 with FastAPI.
    *   *Justification:* FastAPI offers excellent asynchronous support, essential for real-time audio streaming and concurrent API calls. Python 3.12 provides the latest language features. Pydantic integration simplifies data validation and serialization.
*   **AI Model & SDK:** Google Gemini 2.0 Flash Live Preview (`gemini-2.0-flash-live-preview-04-09`) via Google ADK.
    *   *Justification:* This is the only model used for real-time voice handling, mandated by project requirements for its real-time conversational AI capabilities and audio streaming support.
*   **Telephony:** Twilio Programmable Voice.
    *   *Justification:* Required for handling voice calls, call control, and audio streaming.
*   **Asynchronous Task Queue (Potentially for non-realtime tasks):** Celery with Redis 
    *   *Justification:* While the agent aims to be real-time, if any post-call processing tasks become complex (e.g., detailed analytics preparation before sending to web backend, though currently not a primary feature), Celery would be used. For now, FastAPI's `BackgroundTasks` might suffice for simple post-call actions like notifying the web backend.
*   **Authentication Method (with Web Backend):** API Key-based (`X-API-Key` header).
    *   *Justification:* Aligns with the existing Web Backend's authentication mechanism for service-to-service communication, ensuring consistency and leveraging established security patterns.
*   **Containerization:** Docker.
    *   *Justification:* Ensures consistent deployment environments across development, staging, and production on Render.com. Simplifies dependency management.

## 3. System Architecture & Component Design

```mermaid
graph TD
    UserCaller --"Voice Call"--> Twilio

    subgraph AIAgentBackend (FastAPI on Render.com)
        AIAgentAPI[FastAPI Application]
        GeminiADK[Google ADK Integration]
        AudioProc[Audio Processing & Streaming]
        ConfigMgmt[Configuration Manager]
        CallCtrl[Call Control Logic]
        WebBackendClient[Web Backend API Client]
    end

    subgraph WebBackend (Existing Service)
        WebBackendAPI[Web Backend APIs]
        Database[(Business & App DB)]
    end

    Twilio --"Webhook (Incoming Call)"--> AIAgentAPI
    AIAgentAPI --"Stream Audio/Events"--> GeminiADK
    GeminiADK --"AI Responses/Audio"--> AIAgentAPI
    AIAgentAPI --"Stream Audio Out"--> Twilio
    AIAgentAPI --"Call Control (Hangup, Record)"--> Twilio

    AIAgentAPI --"POST Call Recording URL, Transcript"--> WebBackendClient
    WebBackendClient --"POST /call_logs"--> WebBackendAPI
    WebBackendAPI --"Store Data"--> Database

    AIAgentAPI --"GET Business/Agent Config, Verify Call"--> WebBackendClient
    WebBackendClient --"GET /internal/..., POST /verify-call-reception"--> WebBackendAPI
    WebBackendAPI --"Fetch Data"--> Database

    Twilio --"Store Call Recording"--> Twilio[(Twilio Storage)]
    AIAgentAPI --"Extract Recording URL"--> Twilio
```

**Major Components/Services (AI Agent Backend):**

*   **FastAPI Application (`AIAgentAPI`):**
    *   **Primary Purpose:** Main entry point for Twilio webhooks, handles HTTP requests, orchestrates call flows, and manages interactions with other components.
    *   **Key Responsibilities:**
        *   Receive incoming call notifications from Twilio.
        *   Manage WebSocket connections for real-time audio streaming with Twilio (if using TwiML Bins or similar for direct streaming) or handle audio chunks via HTTP.
        *   Route requests to appropriate handlers (e.g., pre-call verification, conversation handling).
        *   Implement API endpoints for Twilio interaction.
*   **Google ADK Integration (`GeminiADK` / `app.gemini_integration.streaming.GeminiStreamingClient`):
    *   **Primary Purpose:** Interface with the Google Gemini 2.0 Live model using the Google Agent Development Kit (ADK).
    *   **Key Responsibilities (derived from MVP's `adk_agent.py` and `streaming.py`):
        *   **Vertex AI Authentication Setup (`adk_agent.setup_vertexai_auth`, `streaming.GeminiStreamingClient._verify_vertexai_auth`):**
            *   Reads `google_application_credentials`, `google_cloud_project`, `google_cloud_location` from `app.config.settings`.
            *   Sets corresponding environment variables (`GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`).
            *   Crucially sets `os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"` if `settings.google_genai_use_vertexai` is true.
        *   **ADK Agent Definition (`adk_agent.root_agent`):
            *   A global `Agent` instance is created: `Agent(name="twilio_voice_assistant", model=settings.gemini_model, instruction=settings.system_prompt)`.
        *   **Session Management (`streaming.GeminiStreamingClient`):
            *   Uses `InMemorySessionService()`.
            *   `start_session(session_id)` method:
                *   Creates an ADK session: `self.session_service.create_session(app_name="TwilioGeminiADK", user_id=session_id, session_id=session_id)`.
                *   Creates an ADK `Runner`: `Runner(app_name="TwilioGeminiADK", agent=self.root_agent, session_service=self.session_service)`.
        *   **Run Configuration (`streaming.GeminiStreamingClient.start_session`):
            *   Defines `speech_config` using `genai_types.SpeechConfig` and `genai_types.VoiceConfig` (e.g., `PrebuiltVoiceConfig(voice_name=settings.gemini_voice_name or "Puck")`).
            *   Constructs `run_config_dict` with `response_modalities=[Modality.AUDIO]`, the `speech_config`, `output_audio_transcription={}`, and `input_audio_transcription={}`.
            *   Creates `RunConfig(**run_config_dict)`.
        *   **Live Interaction (`streaming.GeminiStreamingClient.start_session`):
            *   Creates a `LiveRequestQueue()`.
            *   Starts the live run: `self.live_events = self.runner.run_live(session=self.adk_session, live_request_queue=self.live_request_queue, run_config=run_config)`.
        *   **Audio & Event Handling (`streaming.GeminiStreamingClient`):
            *   `send_audio_chunk(audio_bytes)`: Puts `LiveRequest(input_audio=audio_bytes)` onto the `_audio_send_queue` which is then processed by `_send_adk_loop` to send to `self.live_request_queue.put_nowait(...)`.
            *   `signal_end_of_user_turn()`: Puts `LiveRequest(end_user_turn=True)` onto the `live_request_queue`.
            *   `_process_agent_events_loop()`: Asynchronously iterates `self.live_events`.
                *   Handles `AgentOutputAudio`: Extracts audio bytes, calls `self._audio_output_callback(audio_bytes)`.
                *   Handles `AgentOutputText`: Extracts text, calls `self._text_output_callback(text)`.
            *   Sets up callbacks (`_audio_output_callback`, `_text_output_callback`) to integrate with the Twilio WebSocket handler.
        *   **Cleanup (`stop_session`, `_cleanup_session_objects`):** Manages closing queues, canceling tasks, and potentially ADK cleanup methods.
*   **Audio Processing & Streaming (`AudioProc` / `app.audio_processing.utils.audio_processor`):
    *   **Primary Purpose:** Handle real-time audio data conversion and streaming between Twilio and the Gemini ADK component.
    *   **Key Responsibilities (derived from MVP's `audio_processing/utils.py` and `twilio_integration/websockets.py`):
        *   **Twilio to Gemini Audio Path (`websockets.TwilioMediaStreamHandler._handle_media_message` calling `audio_processor.process_twilio_to_gemini`):
            1.  Receives base64 encoded audio payload from Twilio (8kHz mulaw).
            2.  `audio_processor.process_twilio_to_gemini` performs:
                *   Base64 decoding.
                *   Mulaw decoding to PCM.
                *   Resampling from 8kHz to 24kHz PCM for Gemini Live.
                *   **Rationale for 24kHz:** Gemini 2.0 Flash Live Preview requires 24kHz sample rate for optimal voice processing and natural language understanding.
                *   **Quality Consideration:** Upsampling from 8kHz to 24kHz provides the required format while maintaining acceptable audio quality for conversation.
            3.  The resulting 24kHz PCM audio chunk is passed to `gemini_client.send_audio_chunk()`.
        *   **Gemini to Twilio Audio Path (`websockets.TwilioMediaStreamHandler._send_audio_to_twilio` calling `audio_processor.process_gemini_to_twilio`):
            1.  Receives audio bytes from Gemini (24kHz PCM).
            2.  `audio_processor.process_gemini_to_twilio` performs:
                *   Resampling from 24kHz to 8kHz.
                *   **Twilio Requirement:** Twilio's media streaming requires 8kHz mulaw format for telephony compatibility.
                *   PCM to mulaw encoding.
                *   Base64 encoding of the mulaw audio.
            3.  The resulting base64 string is sent back to Twilio via WebSocket `media` message.
        *   **Audio Format Configuration:** Relies heavily on `settings` from `app.config.py` for sample rates (`input_sample_rate`, `gemini_input_sample_rate`, `gemini_output_sample_rate`, `output_sample_rate`).
        *   **WebSocket Connection and Session Management:**
            *   **WebSocket Connection Lifecycle:** Each incoming call establishes a dedicated WebSocket connection for media streaming that remains active throughout the entire call duration with automatic reconnection logic for temporary network issues.
            *   **Session State Management:** Each call maintains a unique session ID linking Twilio call SID to Gemini session, including call context, conversation history, and current audio streams.
            *   **Concurrent Call Handling:** Each call operates in its own async context with dedicated resources and no shared state between concurrent calls to prevent interference.
        *   **Debugging:** MVP includes `settings.save_debug_audio` to save intermediate audio files, which is useful for troubleshooting audio conversion issues.
*   **Configuration Manager (`ConfigMgmt`):
    *   **Primary Purpose:** Fetch and manage AI agent configurations.
    *   **Key Responsibilities:**
        *   Retrieve agent name, tone, greeting messages, legal disclaimers, custom questions, FAQs, max call duration, etc., from the Web Backend using `WebBackendClient`.
*   **Call Control Logic (`CallCtrl`):
    *   **Primary Purpose:** Implement the business logic for call handling.
    *   **Key Responsibilities:**
        *   Initiate conversations based on fetched configurations.
        *   Handle pre-call verification (checking customer status and credits via `WebBackendClient`).
        *   Implement logic for max call duration, 1-800 blocking, and sales call detection (based on Gemini's output and configuration).
        *   Manage call hang-up procedures.
        *   Start call recording with Twilio at the beginning of the call.
        *   Extract Twilio recording URLs from Twilio API after call completion.
        *   Post recording URLs to the Web Backend via call logs (Web Backend handles downloading from Twilio).
        *   Collect and format transcriptions for posting to the Web Backend.
*   **Web Backend API Client (`WebBackendClient`):
    *   **Primary Purpose:** Centralized module for all communications with the Web Backend APIs.
    *   **Key Responsibilities:**
        *   Make authenticated API calls to endpoints like `POST /api/v1/businesses/verify-call-reception`, `GET /api/v1/internal/businesses/{business_id}`, `GET /api/v1/internal/ai-agent/{business_id}/config`, `POST /api/v1/call_logs`.
        *   Handle API responses, error handling, and retries (if applicable).
        *   No caching strategy implemented - all requests fetch fresh data from the Web Backend to ensure consistency.

## 4. Data Structure Design

As the AI Agent is stateless, it does not have its own database schema. However, it will use Pydantic models to represent data exchanged with the Web Backend and for internal data handling.

**Application-Layer Data Models (Pydantic `BaseModel`):**

These models will largely mirror the schemas defined in `webbackend_api_update_specification.md` for requests made *to* the Web Backend and responses received *from* it.

```python
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime

# --- Models for interacting with Web Backend (based on webbackend_api_update_specification.md) ---

class VerifyCallReceptionRequest(BaseModel):
    to_phone_number: str # E.164 format

class VerifyCallReceptionResponse(BaseModel):
    can_receive_call: bool
    reason_code: str # Enum: OK, NOT_CUSTOMER, INSUFFICIENT_CREDITS, INTERNAL_NUMBER, API_ERROR
    reason_message: str
    business_id: Optional[uuid.UUID] = None
    current_credit_balance: Optional[float] = None

class EventNotificationDetails(BaseModel):
    customer_phone_number: str
    attempted_caller_phone_number: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None

class EventNotificationRequest(BaseModel):
    event_type: str # Enum: INSUFFICIENT_CREDITS_CALL_ATTEMPT, CALL_FAILED, CALL_REJECTED, etc.
    event_timestamp: datetime
    details: EventNotificationDetails

class BusinessHour(BaseModel):
    day_of_week: int # 0-6
    open_time: str # HH:MM format
    close_time: str # HH:MM format
    is_closed: bool

class CoreService(BaseModel):
    service_name: str
    description: str

class BusinessInfoResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    phone_number: str
    business_hours: List[BusinessHour]
    core_services: List[CoreService]
    timezone: str
    address: Optional[str] = None
    website: Optional[HttpUrl] = None

class FAQItem(BaseModel):
    question: str
    answer: str
    display_order: int

class CustomQuestion(BaseModel):
    question_text: str
    expected_answer_type: str
    is_required: bool

class AgentTone(str, Enum):
    CASUAL = "casual"
    CHEERFUL = "cheerful"
    FORMAL = "formal"

class AIAgentConfigResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    agent_name: str
    greeting_message: str
    legal_disclaimer: str  # Plain English sentences without placeholder variables
    tone: AgentTone
    max_call_duration_minutes: int
    enable_1800_blocking: bool
    enable_sales_detection: bool
    voicemail_instructions: str
    call_forwarding_number: Optional[str] = None  # Placeholder, not implemented in first phase
    call_forwarding_enabled: bool  # Placeholder, not implemented in first phase
    faq_list: List[FAQItem]
    custom_questions: List[CustomQuestion]

class CallStatus(str, Enum):
    ANSWERED_BY_AI = "answered_by_ai"
    FORWARDED = "forwarded"
    MISSED = "missed"
    VOICEMAIL = "voicemail"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class CallNotAnsweredReason(str, Enum):
    NOT_CUSTOMER = "not_customer"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    BLOCKED_1800 = "1800_blocked"
    SALES_DETECTED = "sales_detected"
    TECHNICAL_ERROR = "technical_error"

class TechnicalErrorCode(str, Enum):
    NETWORK_ERROR = "network_error"
    API_TIMEOUT = "api_timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_PHONE_FORMAT = "invalid_phone_format"
    AUTHENTICATION_FAILED = "authentication_failed"

class CallLogAnswerCreate(BaseModel):
    question_asked: str = Field(min_length=1)
    answer_provided: Optional[str] = None

class CallLogCreateRequest(BaseModel):
    # Required fields
    caller_phone_number: str = Field(max_length=30)  # E.164 format, caller's phone number
    call_start_time: datetime  # ISO 8601 format, when the call started
    call_status: CallStatus  # enum, status of the call
    business_id: uuid.UUID  # ID of the business receiving the call
    
    # Optional fields
    call_end_time: Optional[datetime] = None  # When the call ended
    call_duration_seconds: Optional[int] = Field(None, ge=0)  # Duration in seconds (>=0)
    ai_summary: Optional[str] = None  # AI-generated summary of the call
    full_transcript: Optional[str] = None  # Full transcript of the call
    recording_url: Optional[str] = None  # URL to the call recording
    answers: Optional[List[CallLogAnswerCreate]] = None  # List of Q&A pairs
    
    # New AI agent enhancement fields
    twilio_call_sid: Optional[str] = Field(None, max_length=100)  # Twilio call SID
    call_not_answered_reason: Optional[CallNotAnsweredReason] = None  # Why call wasn't answered
    ai_agent_version: Optional[str] = Field(None, max_length=50)  # AI agent version
    gemini_model_version: Optional[str] = Field(None, max_length=50)  # Gemini model version
    technical_error_code: Optional[TechnicalErrorCode] = None  # Specific technical error

# --- Internal AI Agent Models (example) ---

class CallContext(BaseModel):
    call_sid: str # Twilio Call SID
    to_phone_number: str
    from_phone_number: str
    business_id: Optional[uuid.UUID] = None
    agent_config: Optional[AIAgentConfigResponse] = None
    conversation_transcript: List[str] = Field(default_factory=list) # e.g., ["agent: Hello", "caller: Hi"]
    start_time: datetime = Field(default_factory=datetime.utcnow)
    # ... other relevant context for an active call

```

## 5. API Endpoint Design (AI Agent Internal & External Interactions)

The AI Agent primarily consumes APIs from the Web Backend. It will expose webhook endpoints for Twilio.

**Twilio Webhook Endpoints (Exposed by AI Agent):**

| HTTP Method | Endpoint Path                      | Description                                                                 | Authentication | Request Body (Simplified)         | Response (TwiML)                                  |
|-------------|------------------------------------|-----------------------------------------------------------------------------|----------------|-----------------------------------|---------------------------------------------------|
| `POST`      | `/twilio-voice`                    | Handles incoming call notifications from Twilio. Initiates pre-call checks. | Twilio Sig.    | Twilio Voice Request Parameters | TwiML to connect call, play audio, gather, etc. |
| `POST`      | `/twilio-status`                   | Receives call status updates (e.g., completed, failed).                     | Twilio Sig.    | Twilio Status Callback Parameters | Empty 200 OK                                      |
| `POST`      | `/twilio-recording-status`         | Receives recording status updates from Twilio. Extracts recording URLs.     | Twilio Sig.    | Twilio Recording Status Parameters | Empty 200 OK                                      |
| `WEBSOCKET` | `/media-stream`                    | Handles bi-directional audio streaming with Twilio. Twilio connects to this endpoint after receiving TwiML with `<Connect><Stream url="wss://...">`. | Twilio Sig.  | JSON messages (Twilio Media Stream protocol: `start`, `media`, `stop`, `mark`) | JSON messages (Twilio Media Stream protocol: `media`, `mark`, `clear`) |

**Web Backend API Endpoints (Consumed by AI Agent):**

These are defined in `webbackend_api_update_specification.md`. The AI Agent will be a client to these APIs.

| HTTP Method | Endpoint Path                                          | Description                                                                                                | Authentication (by AI Agent) |
|-------------|--------------------------------------------------------|------------------------------------------------------------------------------------------------------------|------------------------------|
| `POST`      | `/api/v1/businesses/verify-call-reception`             | Verifies if the 'to' number can receive a call (customer, credits).                                        | `X-API-Key`                  |
| `GET`       | `/api/v1/internal/businesses/{business_id}`            | Fetches detailed business information.                                                                     | `X-API-Key`                  |
| `GET`       | `/api/v1/internal/ai-agent/{business_id}/config`       | Fetches AI agent specific configuration (greetings, FAQs, tone, etc.).                                     | `X-API-Key`                  |
| `POST`      | `/api/v1/businesses/notify-event`                      | Notifies web backend of significant AI agent events (e.g., call rejected due to no credits).             | `X-API-Key`                  |
| `POST`      | `/api/v1/call_logs` (or similar for creating call logs) | Posts call details, transcript, and recording URL to the web backend after a call.                       | `X-API-Key`                  |

## 6. Implementation Guidelines & Best Practices

*   **Project Structure (FastAPI Backend):**

    ```
    /ai_agent_backend
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                     # FastAPI app instantiation, middleware, lifespan events
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       └── endpoints/
    │   │           ├── __init__.py
    │   │           └── twilio_webhooks.py  # Endpoints for Twilio
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── config.py               # Pydantic Settings model for env vars
    │   │   └── security.py             # API key verification for web backend (if agent exposes APIs)
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── call_handler.py         # Main logic for handling a call lifecycle
    │   │   ├── gemini_service.py       # Interaction with Google ADK / Gemini
    │   │   ├── twilio_service.py       # Twilio client interactions (sending TwiML, hangup, recording management)
    │   │   └── web_backend_client.py   # Client for Web Backend APIs
    │   ├── models/
    │   │   ├── __init__.py
    │   │   └── pydantic_models.py      # Pydantic models for API requests/responses & internal data
    │   └── utils/
    │       ├── __init__.py
    │       └── audio_utils.py          # Audio processing utilities (if any)
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py
    │   ├── unit/
    │   └── integration/
    ├── .env.example
    ├── .gitignore
    ├── Dockerfile
    ├── requirements.txt
    └── README.md
    ```

*   **Configuration Management:**
    *   Use `.env` files for local development, loaded into a Pydantic `Settings` model (e.g., `app/core/config.py`).
    *   Environment variables on Render.com for production settings.
    *   Securely store `WEB_BACKEND_API_KEY`, `TWILIO_AUTH_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS` (path to the service account key JSON file).
    *   **Key Environment Variables (derived from MVP's `app/config.py`):**
        *   `TWILIO_ACCOUNT_SID`: Twilio Account SID.
        *   `TWILIO_AUTH_TOKEN`: Twilio Authentication Token.
        *   `TWILIO_WEBHOOK_URL`: (Optional) Base URL for constructing Twilio webhook URLs if not dynamically determined from request. The MVP dynamically constructs the WebSocket URL based on the incoming request's hostname for the `/twilio-voice` webhook.
        *   `TWILIO_VALIDATE_SIGNATURE`: Boolean (`True`/`False`) to enable/disable Twilio request signature validation. (MVP default: `True`).
        *   `GOOGLE_APPLICATION_CREDENTIALS`: Path to the Google Cloud service account JSON key file.
        *   `GOOGLE_CLOUD_PROJECT`: Google Cloud Project ID.
        *   `GOOGLE_CLOUD_LOCATION`: Google Cloud region (e.g., `us-central1`).
        *   `GOOGLE_GENAI_USE_VERTEXAI="True"`: Crucial for forcing the Google GenAI SDK/ADK to use Vertex AI backend. (MVP default: `True`).
        *   `GEMINI_MODEL`: Specific Gemini model identifier (`gemini-2.0-flash-live-preview-04-09` - the only model used for real-time voice handling).
        *   `GEMINI_API_VERSION`: API version for Gemini Live (e.g., `v1alpha` in MVP for Live API).
        *   `GEMINI_LANGUAGE_CODE`: Language code for speech recognition and synthesis (e.g., `en-US`).
        *   `GEMINI_VOICE_NAME`: (Optional) Preferred voice for Gemini's speech output (e.g., `Puck`).
        *   `INPUT_SAMPLE_RATE`: Audio sample rate from Twilio (`8000` Hz for mulaw).
        *   `GEMINI_INPUT_SAMPLE_RATE`: Expected audio sample rate by Gemini (`24000` Hz for PCM - required by Gemini 2.0 Flash Live Preview).
        *   `GEMINI_OUTPUT_SAMPLE_RATE`: Audio sample rate from Gemini (`24000` Hz for PCM).
        *   `OUTPUT_SAMPLE_RATE`: Target audio sample rate for Twilio playback (`8000` Hz for mulaw).
        *   `SYSTEM_PROMPT`: The base instruction or persona for the AI agent.
        *   `LOG_LEVEL`: Logging level for the application (e.g., `INFO`, `DEBUG`).
        *   `USE_TWILIO_AUDIO_QUEUE`: Boolean (`True`/`False`) to control whether to use a queue-based system for sending audio to Twilio (MVP default: `True`).
        *   `WEB_BACKEND_BASE_URL`: Base URL for the Web Backend API.
        *   `WEB_BACKEND_API_KEY`: API key for authenticating with the Web Backend.

*   **Error Handling Strategy:**
    *   **Gemini ADK Failures:**
        *   Implement try-catch blocks around all ADK operations as recommended in ADK documentation.
        *   On session failures, attempt to restart the Gemini session once.
        *   If restart fails, gracefully end the call with an apology message.
        *   Log all ADK errors with session context for debugging.
        *   Use ADK's SessionException handling for proper error categorization.
    *   **Web Backend API Timeouts:**
        *   Set 10-second timeout for all Web Backend API calls.
        *   Implement exponential backoff retry (max 3 attempts) for non-critical calls.
        *   For critical pre-call verification failures, end call immediately.
        *   For post-call logging failures, queue for later retry using background tasks.
        *   Provide fallback responses when configuration data is unavailable.
    *   **Audio Processing Errors:**
        *   Handle mulaw/PCM conversion failures gracefully.
        *   Implement audio buffer overflow protection.
        *   Log audio processing errors without exposing sensitive data.
        *   Continue call processing when possible, terminate only on critical audio failures.
    *   **Twilio Recording URL Extraction Failures:**
        *   Retry Twilio API calls to extract recording URLs up to 3 times with exponential backoff.
        *   If recording URL extraction fails, post call log without recording URL and log the failure.
        *   Continue call processing regardless of recording URL extraction status.

*   **Testing Strategy:**
    *   **Unit Tests (`pytest`):**
        *   Test individual functions and classes in `services/`, `core/`, `utils/`.
        *   Mock external dependencies (Twilio API, Gemini ADK, Web Backend API, GCS).
        *   Test Pydantic model validation.

*   **Detailed Google ADK & Gemini Live Integration (from MVP Analysis):**
    *   **Core Files:** `app/config.py`, `app/gemini_integration/adk_agent.py`, `app/gemini_integration/streaming.py`.
    *   **Configuration (`app/config.py`):
        *   Vertex AI: `google_application_credentials`, `google_cloud_project`, `google_cloud_location`, `google_genai_use_vertexai`.
        *   Gemini Model: `gemini_model`, `gemini_api_version`, `gemini_language_code`, `gemini_voice_name`.
        *   Audio: `input_sample_rate`, `gemini_input_sample_rate`, `gemini_output_sample_rate`, `output_sample_rate`.
        *   Prompt: `system_prompt`.
    *   **Authentication (`app/gemini_integration/adk_agent.py` - `setup_vertexai_auth()`):
        *   Sets environment variables: `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`.
        *   Critically sets `os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"` based on `settings.google_genai_use_vertexai`.
        *   This function is called globally in `adk_agent.py` before the `root_agent` is defined.
    *   **ADK Agent Definition (`app/gemini_integration/adk_agent.py`):
        *   `root_agent = Agent(name="twilio_voice_assistant", model=settings.gemini_model, description="...", instruction=settings.system_prompt)`.
    *   **Streaming Client (`app/gemini_integration/streaming.py` - `GeminiStreamingClient`):
        *   **Initialization:** Verifies Vertex AI auth, sets up `InMemorySessionService`, stores `root_agent`.
        *   **`start_session(session_id)`:**
            *   Creates ADK `Session` and `Runner`.
            *   Defines `RunConfig`:
                *   `response_modalities: [Modality.AUDIO]`
                *   `speech_config`: `genai_types.SpeechConfig` with `VoiceConfig` (e.g., `PrebuiltVoiceConfig(voice_name=settings.gemini_voice_name or "Puck")`).
                *   `output_audio_transcription: {}` (to get text of agent speech).
                *   `input_audio_transcription: {}` (to get text of user speech, enables VAD).
            *   Creates `LiveRequestQueue()`.
            *   Starts live run: `self.live_events = self.runner.run_live(...)`.
            *   Starts async tasks: `_process_agent_events_loop()` and `_send_adk_loop()`.
        *   **`_send_adk_loop()`:** Reads from an internal `_audio_send_queue` (where `send_audio_chunk` places data) and puts `LiveRequest(input_audio=...)` into the ADK's `live_request_queue`.
        *   **`send_audio_chunk(audio_bytes)`:** Adds audio to the internal `_audio_send_queue`.
        *   **`signal_end_of_user_turn()`:** Puts `LiveRequest(end_user_turn=True)` directly to ADK's `live_request_queue`.
        *   **`_process_agent_events_loop()`:** Iterates `self.live_events`:
            *   If `AgentOutputAudio`, calls `_audio_output_callback`.
            *   If `AgentOutputText`, calls `_text_output_callback`.
        *   **`stop_session()`:** Cleans up tasks and queues.

*   **Detailed Twilio Integration (from MVP Analysis):**
    *   **Core Files:** `app/config.py`, `app/twilio_integration/webhooks.py`, `app/twilio_integration/websockets.py`.
    *   **Configuration (`app/config.py`):
        *   `twilio_account_sid`, `twilio_auth_token`, `twilio_webhook_url` (optional), `twilio_validate_signature`.
    *   **Incoming Call Webhook (`app/twilio_integration/webhooks.py` - `handle_incoming_call` at `/twilio-voice`):
        *   Validates Twilio signature using `RequestValidator(settings.twilio_auth_token)` if `settings.twilio_validate_signature` is true.
        *   Performs pre-call verification by calling the Web Backend's `verify-call-reception` endpoint.
        *   If verification succeeds, responds with TwiML:
            *   `<Say>`: Initial greeting.
            *   `<Record>`: Starts call recording with recording status callback URL pointing to `/twilio-recording-status` endpoint.
            *   `<Connect><Stream url="wss://{request.url.hostname}/media-stream"></Stream></Connect>`: This is key. It instructs Twilio to open a WebSocket connection to the `/media-stream` endpoint on the same host.
        *   If verification fails, responds with TwiML to politely decline the call.
    *   **WebSocket Handler (`app/twilio_integration/websockets.py` - `TwilioMediaStreamHandler` called by `handle_media_stream` at `/media-stream`):
        *   **Connection:** Accepts WebSocket connection.
        *   **Message Processing (`_process_message`):
            *   `event: "start"` (`_handle_stream_start`):
                *   Receives `streamSid`, `callSid`.
                *   Creates `CallSession` and stores it in `active_sessions`.
                *   Initializes `GeminiStreamingClient`.
                *   Sets callbacks: `_send_audio_to_twilio` for audio output, `_handle_gemini_text_response` for text.
                *   Calls `gemini_client.start_session(session_id=call_sid)`.
            *   `event: "media"` (`_handle_media_message`):
                *   Gets base64 audio `payload`.
                *   Calls `audio_processor.process_twilio_to_gemini(...)`.
                *   Sends processed audio to `gemini_client.send_audio_chunk(...)`.
                *   MVP had a commented-out VAD timer (`_reset_user_speech_timer`) and a placeholder to signal end of turn after each chunk, highlighting the need for robust VAD.
            *   `event: "stop"` (`_handle_stream_stop`):
                *   Cleans up: `gemini_client.stop_session()`, removes from `active_sessions`.
            *   `event: "mark"`:
                *   Logs acknowledgment from Twilio. If `mark.name == "user_finished_speaking"`, it calls `gemini_client.signal_end_of_user_turn()`.
        *   **Sending Audio to Twilio (`_send_audio_to_twilio` via `_audio_sender_loop` and `_audio_queue` if `settings.use_twilio_audio_queue`):
            *   Receives audio bytes from Gemini callback.
            *   Calls `audio_processor.process_gemini_to_twilio(...)` to get base64 audio.
            *   Constructs Twilio `media` JSON message: `{"event": "media", "streamSid": self.stream_sid, "media": {"payload": base64_audio}}`.
            *   Sends a `mark` message *before* the `media` message for better playback synchronization: `{"event": "mark", "streamSid": self.stream_sid, "mark": {"name": f"ai_audio_chunk_{int(time.time()*1000)}"}}`.
            *   Sends the `media` message.
        *   **Cleanup (`_cleanup`):** Stops Gemini client, cancels audio sender task.
    *   **Status Webhook (`app/twilio_integration/webhooks.py` - `handle_call_status` at `/twilio-status`):
        *   Logs call status updates (e.g., `completed`, `failed`).
    *   **Recording Status Webhook (`app/twilio_integration/webhooks.py` - `handle_recording_status` at `/twilio-recording-status`):
        *   Receives recording status updates from Twilio when recordings are available.
        *   Extracts recording URL from the webhook payload.
        *   Stores recording URL for inclusion in call log posted to Web Backend.

*   **Detailed Audio Processing Pipeline (from MVP Analysis - `app.audio_processing.utils.AudioProcessor`):
    *   **Twilio to Gemini (`process_twilio_to_gemini`):
        1.  Input: Base64 encoded string (Twilio 8kHz mulaw).
        2.  Base64 decode.
        3.  Mulaw to PCM conversion (e.g., using `audioop.ulaw2lin`).
        4.  Resample from 8kHz to 24kHz (Gemini input). MVP's `_resample_audio` uses simple linear interpolation if `scipy` is not available, otherwise `scipy.signal.resample_poly` or `resample`.
        5.  Output: 24kHz PCM16 bytes.
    *   **Gemini to Twilio (`process_gemini_to_twilio`):
        1.  Input: PCM bytes (Gemini output, e.g., 24kHz PCM16).
        2.  Resample from 24kHz to 8kHz (Twilio output).
        3.  PCM to Mulaw conversion (e.g., `audioop.lin2ulaw`).
        4.  Base64 encode.
        5.  Output: Base64 encoded string.
    *   **Sample Rates:** Configured via `settings`: `input_sample_rate` (8000), `gemini_input_sample_rate` (24000), `gemini_output_sample_rate` (24000), `output_sample_rate` (8000).
    *   **Debug Audio:** `save_debug_audio` in `settings` controls saving intermediate .wav files.

*   **Testing Strategy:**
    *   **Unit Tests (`pytest`):
        *   Test individual functions and classes in `services/`, `core/`, `utils/`.
        *   Mock external dependencies (Twilio API, Gemini ADK, Web Backend API, GCS).
        *   Test Pydantic model validation.
        *   Specific tests for pre-call verification logic, configuration parsing, transcription formatting.
    *   **Integration Tests (`pytest`, `httpx`):
        *   Test interactions between internal components (e.g., `call_handler` with `gemini_service` and `web_backend_client`).
        *   Test FastAPI endpoints for Twilio webhooks by simulating Twilio requests.
        *   Test interaction with a mock Web Backend API.
    *   **E2E Tests (Potentially manual initially, or using Twilio Dev Phone/APIs):**
        *   Full call flow from an actual phone call through Twilio -> AI Agent -> Gemini -> Twilio.
        *   Verify call recording URL extraction and metadata posting to (a instance of) the Web Backend.
    *   **Code Coverage:** Aim for >85%.
    *   Use `pytest-asyncio` for testing async code.

*   **Logging Strategy:**
    *   Use structured logging (e.g., `python-json-logger`) outputting JSON.
    *   **INFO:** Incoming call events (SID, from/to numbers), call status changes, successful API interactions with Web Backend, configuration loaded, call picked up/ended normally.
    *   **WARN:** Retries for external API calls, unexpected but handled conditions (e.g., slightly malformed Twilio request if recoverable), cache misses for critical config.
    *   **ERROR:** Failed pre-call verification, exceptions during call processing, failed API calls to Web Backend (after retries), Gemini ADK errors, Twilio API errors, unhandled exceptions. Include stack traces and relevant context (e.g., Call SID).
    *   Log all incoming call information (from Twilio webhook) regardless of pickup status, including reason for not picking up.
    *   Log interactions with Gemini ADK (request/response summaries, errors).

*   **Deployment (Render.com):**
    *   Containerize the FastAPI application using the `Dockerfile`.
    *   Deploy as a Render.com Web Service.
    *   Configure environment variables directly in Render.com dashboard (for `WEB_BACKEND_API_KEY`, Twilio credentials, Google Cloud credentials, etc.).
    *   Set up health check endpoints in FastAPI (e.g., `/health`) for Render.com to monitor.
    *   Configure auto-scaling based on CPU/memory usage or request latency if needed.
    *   Ensure Render service has network access to Twilio, Google Cloud APIs, and the Web Backend service.

*   **Twilio Integration Guidelines:**
    *   Secure Twilio webhooks using Twilio's request validation (checking the `X-Twilio-Signature`).
    *   Handle call recording: Configure Twilio to record calls, listen to recording status webhooks, extract recording URLs from Twilio API, and pass URLs to Web Backend via call logs.
    *   Use appropriate TwiML verbs for call control (`<Say>`, `<Stream>`, `<Connect>`, `<Gather>`, `<Hangup>`, `<Record>`).
    *   Manage call state effectively (e.g., active, ended, failed).

    *   **Google ADK & Gemini Integration:**
    *   Follow Google ADK best practices for session management and audio streaming.
    *   Implement robust error handling for ADK interactions.
    *   Pass necessary configurations (agent name, tone, FAQs, custom questions, greeting, disclaimer) to the Gemini model via system prompts or initial messages as appropriate through the ADK.
    *   Handle sales call detection: When `enable_sales_detection` is enabled, include sales detection instructions as part of the system prompt for the AI model. When disabled, exclude this part of the system prompt.
    *   **Voice Activity Detection (VAD):** VAD will be handled automatically by the Gemini 2.0 Flash Live Preview model. No additional VAD implementation is required in the AI Agent.

    *   **Performance Requirements:**
    *   **Latency:** Target <500 millisecond response time from user speech end to AI response start. This 500ms budget relies on verify-call-reception finishing within <200ms before greeting, requiring end-to-end pipeline timing analysis (Twilio → Agent → Web-Backend → Agent → Twilio).
    *   **Concurrent Calls:** Support minimum 10 concurrent calls initially, with horizontal scaling capability (specific Render plan details to be determined during deployment)
    *   **Audio Quality:** Maintain acceptable voice quality through 8kHz↔24kHz conversion pipeline
    *   **Uptime:** Target 99.5% uptime with graceful degradation during failures

*   **Web Backend Integration:**
    *   Always use the `WebBackendClient` for interactions.
    *   **API Key Authentication Flow:**
        *   AI Agent includes `X-API-Key` header in all requests to Web Backend
        *   Web Backend validates the API key and returns 401 if invalid
        *   AI Agent handles 401 responses by logging the error and gracefully ending the call
        *   API key is configured via environment variable `WEB_BACKEND_API_KEY`
        *   All API calls include proper timeout handling (10 seconds) and retry logic (retry semantics to be decided by development team during implementation)
    *   **No Caching Strategy:** Based on architectural decision, the AI Agent will not implement caching. All business configuration and data will be fetched fresh from the Web Backend for each request to ensure data consistency and simplify the architecture.
    *   Handle API errors gracefully (retries with backoff for transient errors, logging for persistent errors).
    *   Ensure the AI Agent sends data (e.g., `CallLogCreateRequest`) in the exact format expected by the Web Backend.
    *   **Recording Management:** AI Agent posts Twilio recording URLs to Web Backend. Web Backend is responsible for downloading recordings from Twilio and storing them appropriately.
    *   **Legal Disclaimer:** Legal disclaimers are plain English sentences (1-2 sentences) without placeholder variables or templating.