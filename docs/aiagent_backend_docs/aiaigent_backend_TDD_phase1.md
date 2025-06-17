# AI Agent Backend - Technical Design Document (TDD) - Phase 1

**Document Version**: 1.0  
**Date**: June 16, 2025
**Author**: AI Backend Architect

## 1. Overview & Executive Summary

This document outlines the technical design for the AI Agent backend service. The AI Agent is responsible for handling incoming calls via Twilio, interacting with users using Google Gemini 2.0 Live model via Google ADK, and communicating with the existing Web Backend for business logic and data retrieval. This TDD focuses on building a stateless, scalable, and secure FastAPI application deployed on Render.com, designed to integrate seamlessly with the Web Backend and Twilio services.

The core problem being solved is the automated handling of customer calls for Small and Medium-sized Businesses (SMBs) when owners are unavailable, providing a conversational AI experience.

**Key Architectural Decisions & Justifications:**

*   **FastAPI Framework:** Chosen for its high performance, asynchronous capabilities (crucial for real-time audio streaming and API calls), automatic data validation (Pydantic), and OpenAPI documentation generation, which aligns with the project's need for efficient development and clear API contracts.
*   **Stateless Design:** The AI Agent will not maintain its own database. All persistent data (business configurations, call logs, user information) will be managed by the existing Web Backend. This simplifies the AI Agent's architecture, enhances scalability, and centralizes data management.
*   **Google ADK with Gemini 2.0 Live:** Leveraged for advanced conversational AI capabilities, including real-time audio processing and natural language understanding, as specified in the requirements.
*   **Twilio Integration:** Used for all telephony interactions, including receiving incoming calls, streaming audio to/from the AI model, and managing call lifecycle (hang-ups, recordings).
*   **Render.com Deployment:** Selected for its ease of use for deploying containerized Python applications, managed services (like Redis if needed for caching API responses from web backend, though agent itself is stateless), and scalability options.
*   **Web Backend API Consumption:** The AI Agent will rely heavily on the Web Backend's APIs (as specified in `webbackend_api_update_specification.md`) for pre-call verification, fetching business/agent configurations, and posting call logs/recordings. This ensures a single source of truth for business data.
*   **Security via API Keys:** Service-to-service communication between the AI Agent and the Web Backend will be secured using API keys (`X-API-Key`), as already established in the Web Backend.

## 2. Technology Stack Selection

*   **Language/Framework:** Python 3.12 with FastAPI.
    *   *Justification:* FastAPI offers excellent asynchronous support, essential for real-time audio streaming and concurrent API calls. Python 3.12 provides the latest language features. Pydantic integration simplifies data validation and serialization.
*   **AI Model & SDK:** Google Gemini 2.0 Flash Live Preview (e.g., `gemini-2.0-flash-live-preview-04-09`) via Google ADK.
    *   *Justification:* Mandated by project requirements for its real-time conversational AI capabilities and audio streaming support.
*   **Telephony:** Twilio Programmable Voice.
    *   *Justification:* Required for handling voice calls, call control, and audio streaming.
*   **Asynchronous Task Queue (Potentially for non-realtime tasks):** Celery with Redis 
    *   *Justification:* While the agent aims to be real-time, if any post-call processing tasks become complex (e.g., detailed analytics preparation before sending to web backend, though currently not a primary feature), Celery would be used. For now, FastAPI's `BackgroundTasks` might suffice for simple post-call actions like notifying the web backend.
*   **Authentication Method (with Web Backend):** API Key-based (`X-API-Key` header).
    *   *Justification:* Aligns with the existing Web Backend's authentication mechanism for service-to-service communication, ensuring consistency and leveraging established security patterns.
*   **Containerization:** Docker.
    *   *Justification:* Ensures consistent deployment environments across development, staging, and production on Render.com. Simplifies dependency management.
*   **Permanent Storage (for Recordings):** Google Cloud Storage.
    *   *Justification:* Specified in requirements for storing call recordings. The AI Agent will upload recordings here and provide the URL to the Web Backend.
*   **Caching Layer (for Web Backend API responses):** Redis ( deployed on Render.com and shared caching is beneficial across multiple agent instances).
    *   *Justification:* To reduce latency and load on the Web Backend for frequently accessed, less volatile data like business configurations. The pre-call verification API response from the web backend already suggests caching business info.

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

    Twilio --"Store Call Recording"--> GCS[Google Cloud Storage]
    AIAgentAPI --"Upload Recording (via Twilio SDK or direct)"--> GCS
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
            1.  Receives base64 encoded audio payload from Twilio (typically 8kHz mulaw).
            2.  `audio_processor.process_twilio_to_gemini` likely performs:
                *   Base64 decoding.
                *   Mulaw decoding to PCM.
                *   Resampling from `settings.input_sample_rate` (8kHz) to `settings.gemini_input_sample_rate` (16kHz).
            3.  The resulting 16kHz PCM audio chunk is passed to `gemini_client.send_audio_chunk()`.
        *   **Gemini to Twilio Audio Path (`websockets.TwilioMediaStreamHandler._send_audio_to_twilio` calling `audio_processor.process_gemini_to_twilio`):
            1.  Receives audio bytes from Gemini (via callback, typically `settings.gemini_output_sample_rate` e.g., 24kHz PCM).
            2.  `audio_processor.process_gemini_to_twilio` likely performs:
                *   Resampling from `settings.gemini_output_sample_rate` (24kHz) to `settings.output_sample_rate` (8kHz).
                *   PCM to mulaw encoding.
                *   Base64 encoding of the mulaw audio.
            3.  The resulting base64 string is sent back to Twilio via WebSocket `media` message.
        *   **Audio Format Configuration:** Relies heavily on `settings` from `app.config.py` for sample rates (`input_sample_rate`, `gemini_input_sample_rate`, `gemini_output_sample_rate`, `output_sample_rate`).
        *   **Debugging:** MVP includes `settings.save_debug_audio` to save intermediate audio files, which is useful for troubleshooting audio conversion issues.
*   **Configuration Manager (`ConfigMgmt`):
    *   **Primary Purpose:** Fetch and manage AI agent configurations.
    *   **Key Responsibilities:**
        *   Retrieve agent name, tone, greeting messages, legal disclaimers, custom questions, FAQs, max call duration, etc., from the Web Backend using `WebBackendClient`.
        *   Cache configurations locally (in-memory with TTL or Redis) to minimize repeated API calls to the Web Backend.
*   **Call Control Logic (`CallCtrl`):
    *   **Primary Purpose:** Implement the business logic for call handling.
    *   **Key Responsibilities:**
        *   Initiate conversations based on fetched configurations.
        *   Handle pre-call verification (checking customer status and credits via `WebBackendClient`).
        *   Implement logic for max call duration, 1-800 blocking, and sales call detection (based on Gemini's output and configuration).
        *   Manage call hang-up procedures.
        *   Orchestrate call recording uploads to GCS and posting metadata to the Web Backend.
        *   Collect and format transcriptions for posting to the Web Backend.
*   **Web Backend API Client (`WebBackendClient`):
    *   **Primary Purpose:** Centralized module for all communications with the Web Backend APIs.
    *   **Key Responsibilities:**
        *   Make authenticated API calls to endpoints like `POST /api/v1/businesses/verify-call-reception`, `GET /api/v1/internal/businesses/{business_id}`, `GET /api/v1/internal/ai-agent/{business_id}/config`, `POST /api/v1/call_logs`.
        *   Handle API responses, error handling, and retries (if applicable).
        *   Implement caching for responses from the Web Backend where appropriate (e.g., business/agent configuration).

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
    legal_disclaimer_template: str
    tone: AgentTone
    max_call_duration_minutes: int
    enable_1800_blocking: bool
    enable_sales_detection: bool
    voicemail_instructions: str
    call_forwarding_number: Optional[str] = None
    call_forwarding_enabled: bool
    faq_list: List[FAQItem]
    custom_questions: List[CustomQuestion]

class CallNotAnsweredReason(str, Enum):
    NOT_CUSTOMER = "not_customer"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    BLOCKED_1800 = "1800_blocked"
    SALES_DETECTED = "sales_detected"
    TECHNICAL_ERROR = "technical_error"

class CallLogCreateRequest(BaseModel):
    # Fields to be sent to the Web Backend's CallLogCreate schema
    # This will include fields like business_id, caller_phone_number, transcript_text, recording_url, etc.
    # Refer to webbackend_api_update_specification.md for the full schema expected by the web backend.
    # Example subset:
    business_id: uuid.UUID
    caller_phone_number: str
    call_start_time: datetime
    call_end_time: datetime
    duration_seconds: int
    transcript_text: Optional[str] = None
    recording_url: Optional[HttpUrl] = None
    twilio_call_sid: Optional[str] = Field(None, max_length=100)
    call_not_answered_reason: Optional[CallNotAnsweredReason] = None
    ai_agent_version: Optional[str] = Field(None, max_length=50)
    gemini_model_version: Optional[str] = Field(None, max_length=50)
    # ... other fields as per web backend's CallLogCreate schema

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
| `POST`      | `/twilio/voice/incoming`           | Handles incoming call notifications from Twilio. Initiates pre-call checks. | Twilio Sig.    | Twilio Voice Request Parameters | TwiML to connect call, play audio, gather, etc. |
| `POST`      | `/twilio/voice/status`             | Receives call status updates (e.g., completed, failed).                     | Twilio Sig.    | Twilio Status Callback Parameters | Empty 200 OK                                      |
| `WEBSOCKET` | `/media-stream`                    | Handles bi-directional audio streaming with Twilio. Twilio connects to this endpoint after receiving TwiML with `<Connect><Stream url="wss://...">`. | Twilio Sig. (on initial HTTP upgrade, though not explicitly shown in MVP's WebSocket handler, but good practice) | JSON messages (Twilio Media Stream protocol: `start`, `media`, `stop`, `mark`) | JSON messages (Twilio Media Stream protocol: `media`, `mark`, `clear`) |
| `POST`      | `/twilio/voice/recording_status`   | Receives recording status updates from Twilio.                              | Twilio Sig.    | Twilio Recording Status Params  | Empty 200 OK                                      |

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
    │   │   ├── twilio_service.py       # Twilio client interactions (sending TwiML, hangup, etc.)
    │   │   ├── web_backend_client.py   # Client for Web Backend APIs
    │   │   └── recording_service.py    # Handling call recordings (upload to GCS)
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
    *   Securely store `WEB_BACKEND_API_KEY`, `TWILIO_AUTH_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS` (path to the service account key JSON file), GCS bucket details.
    *   **Key Environment Variables (derived from MVP's `app/config.py`):**
        *   `TWILIO_ACCOUNT_SID`: Twilio Account SID.
        *   `TWILIO_AUTH_TOKEN`: Twilio Authentication Token.
        *   `TWILIO_WEBHOOK_URL`: (Optional) Base URL for constructing Twilio webhook URLs if not dynamically determined from request. The MVP dynamically constructs the WebSocket URL based on the incoming request's hostname for the `/twilio-voice` webhook.
        *   `TWILIO_VALIDATE_SIGNATURE`: Boolean (`True`/`False`) to enable/disable Twilio request signature validation. (MVP default: `True`).
        *   `GOOGLE_APPLICATION_CREDENTIALS`: Path to the Google Cloud service account JSON key file.
        *   `GOOGLE_CLOUD_PROJECT`: Google Cloud Project ID.
        *   `GOOGLE_CLOUD_LOCATION`: Google Cloud region (e.g., `us-central1`).
        *   `GOOGLE_GENAI_USE_VERTEXAI="True"`: Crucial for forcing the Google GenAI SDK/ADK to use Vertex AI backend. (MVP default: `True`).
        *   `GEMINI_MODEL`: Specific Gemini model identifier (e.g., `gemini-2.0-flash-live-preview-04-09`).
        *   `GEMINI_API_VERSION`: API version for Gemini Live (e.g., `v1alpha` in MVP for Live API).
        *   `GEMINI_LANGUAGE_CODE`: Language code for speech recognition and synthesis (e.g., `en-US`).
        *   `GEMINI_VOICE_NAME`: (Optional) Preferred voice for Gemini's speech output (e.g., `Puck`).
        *   `INPUT_SAMPLE_RATE`: Audio sample rate from Twilio (e.g., `8000` Hz for mulaw, as per MVP).
        *   `GEMINI_INPUT_SAMPLE_RATE`: Expected audio sample rate by Gemini (e.g., `16000` Hz for PCM16, as per MVP).
        *   `GEMINI_OUTPUT_SAMPLE_RATE`: Audio sample rate from Gemini (e.g., `24000` Hz for PCM16, as per MVP).
        *   `OUTPUT_SAMPLE_RATE`: Target audio sample rate for Twilio playback (e.g., `8000` Hz for mulaw, as per MVP).
        *   `SYSTEM_PROMPT`: The base instruction or persona for the AI agent.
        *   `LOG_LEVEL`: Logging level for the application (e.g., `INFO`, `DEBUG`).
        *   `USE_TWILIO_AUDIO_QUEUE`: Boolean (`True`/`False`) to control whether to use a queue-based system for sending audio to Twilio (MVP default: `True`).

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
        *   Responds with TwiML:
            *   `<Say>`: Initial greeting.
            *   `<Connect><Stream url="wss://{request.url.hostname}/media-stream"></Stream></Connect>`: This is key. It instructs Twilio to open a WebSocket connection to the `/media-stream` endpoint on the same host.
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

*   **Detailed Audio Processing Pipeline (from MVP Analysis - `app.audio_processing.utils.AudioProcessor`):
    *   **Twilio to Gemini (`process_twilio_to_gemini`):
        1.  Input: Base64 encoded string (Twilio 8kHz mulaw).
        2.  Base64 decode.
        3.  Mulaw to PCM conversion (e.g., using `audioop.ulaw2lin`).
        4.  Resample from 8kHz to 16kHz (Gemini input). MVP's `_resample_audio` uses simple linear interpolation if `scipy` is not available, otherwise `scipy.signal.resample_poly` or `resample`.
        5.  Output: 16kHz PCM16 bytes.
    *   **Gemini to Twilio (`process_gemini_to_twilio`):
        1.  Input: PCM bytes (Gemini output, e.g., 24kHz PCM16).
        2.  Resample from 24kHz to 8kHz (Twilio output).
        3.  PCM to Mulaw conversion (e.g., `audioop.lin2ulaw`).
        4.  Base64 encode.
        5.  Output: Base64 encoded string.
    *   **Sample Rates:** Configured via `settings`: `input_sample_rate` (8000), `gemini_input_sample_rate` (16000), `gemini_output_sample_rate` (24000), `output_sample_rate` (8000).
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
        *   Verify call recording upload and metadata posting to (a test instance of) the Web Backend.
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
    *   Handle call recording: Configure Twilio to record calls, listen to recording status webhooks, download/stream recording from Twilio, and upload to GCS.
    *   Use appropriate TwiML verbs for call control (`<Say>`, `<Stream>`, `<Connect>`, `<Gather>`, `<Hangup>`).
    *   Manage call state effectively (e.g., active, ended, failed).

*   **Google ADK & Gemini Integration:**
    *   Follow Google ADK best practices for session management and audio streaming.
    *   Implement robust error handling for ADK interactions.
    *   Pass necessary configurations (agent name, tone, FAQs, custom questions, greeting, disclaimer) to the Gemini model via system prompts or initial messages as appropriate through the ADK.
    *   Handle sales call detection based on model's output/flags, and implement hang-up logic.

*   **Web Backend Integration:**
    *   Always use the `WebBackendClient` for interactions.
    *   Implement caching with appropriate TTLs for data fetched from the Web Backend (e.g., agent config, business info after `verify-call-reception`).
    *   Handle API errors gracefully (retries with backoff for transient errors, logging for persistent errors).
    *   Ensure the AI Agent sends data (e.g., `CallLogCreateRequest`) in the exact format expected by the Web Backend.