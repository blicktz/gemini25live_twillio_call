# Plan: Integrate Google Gemini Live API for Real-Time Audio Streaming

**Overall Goal:** Refactor the application to use the Google Gemini Live API for real-time, bi-directional audio streaming, specifically targeting the `models/gemini-2.5-flash-preview-native-audio-dialog` model.

**Date:** 2025-06-05

---

## 1. Key API Usage Insights (from Research)

Based on documentation for the Google Gemini Live API:

*   **Client Initialization**: `genai.Client(api_key="YOUR_API_KEY", http_options={'api_version': 'v1alpha'})`. The `v1alpha` API version appears to be necessary for Live API access.
*   **Connecting to Live Session**: `async with client.aio.live.connect(model=MODEL_ID, config=SESSION_CONFIG) as session:`
*   **Sending Data**: `await session.send(input=audio_chunk_or_text, end_of_turn=True/False)`
    *   `input` can be raw audio bytes (for audio chunks) or text strings.
    *   `end_of_turn=True` signals to the model that it can now generate a response.
    *   `end_of_turn=False` is used for streaming continuous input (like audio) before expecting a full response.
*   **Receiving Data**: `async for response in session.receive():`
    *   `response.data` will contain the raw audio bytes if the response modality includes audio.
    *   `response.text` will contain any text parts of the response.
    *   `response.error` can indicate issues during the session.
*   **Audio Formats**:
    *   Input to Gemini: Raw 16-bit PCM audio at 16kHz (little-endian).
    *   Output from Gemini: Raw 16-bit PCM audio at 24kHz (little-endian).
*   **Session Configuration (`config` parameter for `connect`)**:
    *   Example: `{"response_modalities": ["AUDIO", "TEXT"], "language_code": "en-US", "voice": "Puck"}`.
    *   `response_modalities` specifies what kind of output to expect (e.g., audio, text, or both).
    *   `language_code` and `voice` can be used to control the speech output.

---

## 2. Detailed Changes by File

### 2.1. `app/config.py`

*   **Objective**: Update the Gemini model ID to the official Live API model and add new configuration options relevant to the Live API and native audio dialog model.
*   **Proposed Changes**:
    *   Modify `gemini_model` to `models/gemini-2.5-flash-preview-native-audio-dialog`.
    *   Add `gemini_api_version` (e.g., "v1alpha").
    *   Add `gemini_language_code` (e.g., "en-US").
    *   Add `gemini_voice_name` (optional, for explicit voice control, e.g., "Puck").

```python
# app/config.py
import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_webhook_url: Optional[str] = None
    twilio_validate_signature: bool = True

    # Gemini API Configuration
    gemini_api_key: str
    gemini_model: str = "models/gemini-2.5-flash-preview-native-audio-dialog" # UPDATED
    gemini_api_version: str = "v1alpha" # NEW - For Live API
    gemini_language_code: str = "en-US" # NEW - For native audio dialog
    gemini_voice_name: Optional[str] = None # NEW - e.g., "Puck", if we want to specify a voice

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Audio Configuration
    input_sample_rate: int = 8000  # Twilio input sample rate (MuLaw)
    gemini_input_sample_rate: int = 16000  # Gemini expected input (PCM16)
    gemini_output_sample_rate: int = 24000  # Gemini output sample rate (PCM16) - Matches Live API
    output_sample_rate: int = 8000  # Twilio output sample rate (MuLaw)

    # AI Configuration
    system_prompt: str = "You are a friendly and helpful AI assistant answering phone calls. Keep your responses conversational, concise, and natural. Respond as if you're having a real-time voice conversation."
    
    # Logging Configuration (Example - Add if not present and used by Gemini client)
    LOG_LEVEL: str = "INFO"


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings()
```

### 2.2. `app/gemini_integration/streaming.py` (Major Refactor)

*   **Objective**: Rewrite `GeminiStreamingClient` to utilize the Google Gemini Live API for bi-directional audio streaming.
*   **Key Changes**:
    *   Initialize with `genai.Client` configured for the Live API version.
    *   Implement `start_session` using `client.aio.live.connect()` with appropriate model ID and session configuration (response modalities, language, voice).
    *   Send the `initial_prompt` (system prompt) upon session start.
    *   Implement `_send_loop` and `_receive_loop` as internal asyncio tasks:
        *   `_send_loop`: Manages sending queued audio chunks (`end_of_turn=False`) and text messages/signals (`end_of_turn=True`) to the Live API session.
        *   `_receive_loop`: Continuously listens for responses from the Live API session, extracting audio and text data, and invoking callbacks.
    *   Provide `send_audio_chunk(audio_chunk: bytes)` to queue audio for sending.
    *   Provide `signal_end_of_user_turn()` to send an explicit signal (e.g., empty text with `end_of_turn=True`) to prompt Gemini to respond.
    *   Use callbacks (`_audio_output_callback`, `_text_output_callback`) for dispatching received data.
    *   Implement `stop_session` to gracefully cancel tasks and manage session state.

```python
# app/gemini_integration/streaming.py
import asyncio
import logging
from google import generativeai as genai
# from google.generativeai.types import LiveSession # Check actual import if needed for type hints
from app.config import settings
from typing import Callable, Optional

# Configure basic logging (ensure LOG_LEVEL is in settings or handle absence)
log_level_setting = getattr(settings, 'LOG_LEVEL', 'INFO') # Safely get LOG_LEVEL
logging.basicConfig(level=log_level_setting.upper())
logger = logging.getLogger(__name__)

class GeminiStreamingClient:
    def __init__(self, model_name: str = settings.gemini_model):
        self.model_name = model_name
        self.live_session: Optional[genai.live.AsyncLiveSession] = None # Type hint for AsyncLiveSession
        self.is_active = False
        self.client = None
        self._audio_send_queue = asyncio.Queue()
        self._text_send_queue = asyncio.Queue() # For sending explicit text or end-of-turn signals
        self._receive_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None
        self._audio_output_callback: Optional[Callable[[bytes], asyncio.Awaitable[None]]] = None
        self._text_output_callback: Optional[Callable[[str], asyncio.Awaitable[None]]] = None

        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found in settings.")
            raise ValueError("GEMINI_API_KEY must be configured.")

        try:
            self.client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options={'api_version': settings.gemini_api_version}
            )
            logger.info(f"Gemini Client initialized for Live API version '{settings.gemini_api_version}'.")
        except Exception as e:
            logger.exception(f"Failed to initialize Gemini Client: {e}")
            raise

    def set_callbacks(self, 
                      audio_callback: Callable[[bytes], asyncio.Awaitable[None]], 
                      text_callback: Callable[[str], asyncio.Awaitable[None]]):
        self._audio_output_callback = audio_callback
        self._text_output_callback = text_callback

    async def start_session(self, initial_prompt: str = settings.system_prompt):
        if self.is_active:
            logger.warning("Session already active.")
            return

        logger.info(f"Starting Gemini Live API session with model '{self.model_name}'.")
        try:
            session_config = {
                "response_modalities": ["AUDIO", "TEXT"],
                "language_code": settings.gemini_language_code
            }
            if settings.gemini_voice_name:
                session_config["voice"] = settings.gemini_voice_name

            self.live_session = await self.client.aio.live.connect(
                model=self.model_name,
                config=session_config
            )
            logger.info(f"Gemini Live API session connected.")

            if initial_prompt:
                logger.info(f"Sending initial prompt to Gemini Live API: '{initial_prompt}'")
                await self.live_session.send(input=initial_prompt, end_of_turn=True)

            self.is_active = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._send_task = asyncio.create_task(self._send_loop())
            logger.info("Gemini Live API session started successfully, send/receive loops initiated.")

        except Exception as e:
            logger.exception(f"Failed to start Gemini Live API session: {e}")
            self.is_active = False
            self.live_session = None # Ensure session is cleared on failure
            raise

    async def _send_loop(self):
        logger.debug("Gemini send loop started.")
        try:
            while self.is_active and self.live_session:
                text_message_item = None
                audio_chunk_item = None
                
                try: # Check for text message first
                    text_message_item = self._text_send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

                if text_message_item:
                    content = text_message_item['content']
                    eot = text_message_item['end_of_turn']
                    logger.debug(f"Sending text to Gemini: '{content[:50]}...', end_of_turn: {eot}")
                    await self.live_session.send(input=content, end_of_turn=eot)
                    self._text_send_queue.task_done()
                    continue

                try: # Then check for audio chunk
                    audio_chunk_item = self._audio_send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.01) # Small pause if both queues are empty
                    continue
                
                if audio_chunk_item:
                    # logger.debug(f"Sending audio chunk of size {len(audio_chunk_item)} bytes to Gemini.")
                    await self.live_session.send(input=audio_chunk_item, end_of_turn=False)
                    self._audio_send_queue.task_done()
                    
        except asyncio.CancelledError:
            logger.info("Gemini send loop cancelled.")
        except Exception as e:
            logger.exception(f"Error in Gemini send loop: {e}")
            self.is_active = False 
        finally:
            logger.debug("Gemini send loop finished.")

    async def _receive_loop(self):
        logger.debug("Gemini receive loop started.")
        try:
            if not self.live_session:
                logger.error("Receive loop started without an active session.")
                return

            async for response in self.live_session.receive():
                if not self.is_active: break

                if response.data:
                    # logger.debug(f"Received audio data chunk of size {len(response.data)} from Gemini.")
                    if self._audio_output_callback:
                        await self._audio_output_callback(response.data)
                if response.text:
                    logger.info(f"Gemini text response: {response.text}")
                    if self._text_output_callback:
                        await self._text_output_callback(response.text)
                if response.error:
                    logger.error(f"Gemini Live API error in response: {response.error}")
                    self.is_active = False # Stop on error
                    break
        except asyncio.CancelledError:
            logger.info("Gemini receive loop cancelled.")
        except Exception as e:
            logger.exception(f"Error in Gemini receive loop: {e}")
            self.is_active = False
        finally:
            logger.debug("Gemini receive loop finished.")

    async def send_audio_chunk(self, audio_chunk: bytes):
        if not self.is_active:
            # logger.warning("Session not active. Cannot send audio.")
            return
        await self._audio_send_queue.put(audio_chunk)

    async def signal_end_of_user_turn(self):
        if not self.is_active:
            logger.warning("Session not active. Cannot signal end of turn.")
            return
        logger.debug("Signaling end of user turn to Gemini.")
        await self._text_send_queue.put({"content": "", "end_of_turn": True})

    async def stop_session(self):
        if not self.is_active:
            # logger.info("Gemini session already inactive.")
            return

        logger.info("Stopping Gemini Live API session.")
        self.is_active = False 

        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()

        # Wait for tasks to complete cancellation
        if self._send_task:
            try: await self._send_task
            except asyncio.CancelledError: logger.debug("Send task confirmed cancelled.")
        if self._receive_task:
            try: await self._receive_task
            except asyncio.CancelledError: logger.debug("Receive task confirmed cancelled.")
        
        # LiveSession does not have an explicit close() method in the examples.
        # It's typically managed by `async with client.aio.live.connect(...)`.
        # Since we are not using `async with` for the entire client's lifetime here,
        # the session might close when tasks end or due to server-side cleanup.
        # If the SDK provides an explicit close, it should be called.
        # For now, setting live_session to None.
        self.live_session = None
        
        # Clear queues
        while not self._audio_send_queue.empty():
            try: self._audio_send_queue.get_nowait(); self._audio_send_queue.task_done()
            except asyncio.QueueEmpty: break
        while not self._text_send_queue.empty():
            try: self._text_send_queue.get_nowait(); self._text_send_queue.task_done()
            except asyncio.QueueEmpty: break

        logger.info("Gemini Live API session stopped and cleaned up.")

```

### 2.3. `app/twilio_integration/websockets.py`

*   **Objective**: Adapt `TwilioMediaStreamHandler` to integrate with the refactored `GeminiStreamingClient` using the Live API pattern.
*   **Key Changes**:
    *   In `_handle_stream_start`:
        *   Instantiate `GeminiStreamingClient` (model name is now handled by its constructor default).
        *   Call `self.gemini_client.set_callbacks(audio_callback=self._send_audio_to_twilio, text_callback=self._handle_gemini_text_response)`.
        *   `_handle_gemini_text_response` will be a new `async` method to log text from Gemini.
    *   In `_handle_media_message`:
        *   Change `await self.gemini_client.send_audio(pcm_audio)` to `await self.gemini_client.send_audio_chunk(pcm_audio)`.
        *   The direct loop for processing Gemini responses is removed, as this is now handled by the callback mechanism.
        *   **Crucial**: Implement logic for when to call `await self.gemini_client.signal_end_of_user_turn()`. This might involve detecting pauses in Twilio's audio stream or using a timer. For an initial implementation, this might be called after a certain number of chunks or if no new audio arrives from Twilio for a short period. This is a point for refinement.
    *   Ensure `_send_audio_to_twilio` is `async def`.
    *   Add `async def _handle_gemini_text_response(self, text: str):` for logging.
    *   Add `from starlette.websockets import WebSocketState` to imports.

```python
# app/twilio_integration/websockets.py
import json
import logging
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState # ADDED IMPORT
from app.config import settings
from app.core.models import TwilioMediaMessage, TwilioOutboundMedia, CallSession
from app.audio_processing.utils import audio_processor
from app.gemini_integration.streaming import GeminiStreamingClient

logger = logging.getLogger(__name__)
active_sessions: Dict[str, CallSession] = {}

class TwilioMediaStreamHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.call_session: Optional[CallSession] = None
        self.gemini_client: Optional[GeminiStreamingClient] = None
        self.stream_sid: Optional[str] = None
        self.is_active = False
        # TODO: Add a timer or mechanism to detect end of user speech for signal_end_of_user_turn
        self._user_speech_timer: Optional[asyncio.TimerHandle] = None 
        self._silence_threshold_sec = 1.0 # Example: 1 second of silence

    async def handle_connection(self):
        try:
            await self.websocket.accept()
            logger.info("WebSocket connection accepted")
            self.is_active = True
            await self._listen_for_messages()
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
        finally:
            await self._cleanup()

    async def _listen_for_messages(self):
        while self.is_active:
            try:
                message = await self.websocket.receive_text()
                await self._process_message(message)
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during message listening")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                break # Stop listening on error

    async def _process_message(self, message: str):
        try:
            data = json.loads(message)
            msg = TwilioMediaMessage(**data)
            
            if msg.event == "start":
                await self._handle_stream_start(msg)
            elif msg.event == "media":
                await self._handle_media_message(msg)
            elif msg.event == "stop":
                await self._handle_stream_stop(msg)
            elif msg.event == "mark": # Handle mark messages if used for VAD
                logger.debug(f"Received mark event: {msg.mark.name if msg.mark else 'N/A'}")
                if msg.mark and msg.mark.name == "user_finished_speaking": # Example mark name
                     if self.gemini_client and self.gemini_client.is_active:
                        await self.gemini_client.signal_end_of_user_turn()
            else:
                logger.debug(f"Received unknown event: {msg.event}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def _handle_stream_start(self, msg: TwilioMediaMessage):
        try:
            start_data = msg.start
            if not start_data:
                logger.error("No start data in stream start message")
                return
            
            self.stream_sid = start_data.get('streamSid')
            call_sid = start_data.get('callSid')
            logger.info(f"Media stream started: {self.stream_sid} for call: {call_sid}")

            self.call_session = CallSession(call_sid=call_sid, stream_sid=self.stream_sid, is_active=True)
            if call_sid: active_sessions[call_sid] = self.call_session

            self.gemini_client = GeminiStreamingClient() # Uses model from settings by default
            self.gemini_client.set_callbacks(
                audio_callback=self._send_audio_to_twilio,
                text_callback=self._handle_gemini_text_response
            )
            await self.gemini_client.start_session(initial_prompt=settings.system_prompt)
            logger.info(f"Gemini Live API session started for call: {call_sid}")

        except Exception as e:
            logger.error(f"Error handling stream start: {e}", exc_info=True)
            if self.gemini_client and self.gemini_client.is_active:
                await self.gemini_client.stop_session()
            self.gemini_client = None # Ensure it's cleared

    def _reset_user_speech_timer(self):
        if self._user_speech_timer:
            self._user_speech_timer.cancel()
        if self.gemini_client and self.gemini_client.is_active:
            loop = asyncio.get_event_loop()
            self._user_speech_timer = loop.call_later(
                self._silence_threshold_sec, 
                lambda: asyncio.create_task(self.gemini_client.signal_end_of_user_turn())
            )

    async def _handle_media_message(self, msg: TwilioMediaMessage):
        try:
            if not msg.media or not self.gemini_client or not self.gemini_client.is_active:
                return

            audio_payload = msg.media.get('payload')
            if not audio_payload:
                return
            
            # self._reset_user_speech_timer() # Reset timer on receiving new audio

            pcm_audio = audio_processor.process_twilio_to_gemini(
                audio_payload,
                input_rate=settings.input_sample_rate,
                output_rate=settings.gemini_input_sample_rate
            )
            await self.gemini_client.send_audio_chunk(pcm_audio)
            # For simplicity, let's signal end of turn after each chunk for now.
            # This is not ideal for natural conversation but ensures Gemini responds.
            # A better VAD or mark-based system is needed for production.
            await self.gemini_client.signal_end_of_user_turn()


        except Exception as e:
            logger.error(f"Error handling media message: {e}", exc_info=True)

    async def _send_audio_to_twilio(self, audio_data: bytes):
        try:
            if not self.is_active or not self.stream_sid or \
               not self.websocket or self.websocket.client_state != WebSocketState.CONNECTED:
                logger.warning("Cannot send audio to Twilio: WebSocket not active/connected or stream_sid missing.")
                return

            base64_mulaw = audio_processor.process_gemini_to_twilio(
                audio_data,
                input_rate=settings.gemini_output_sample_rate,
                output_rate=settings.output_sample_rate
            )
            outbound_msg = TwilioOutboundMedia(
                event="media", # Ensure event type is media for outbound
                streamSid=self.stream_sid,
                media={"payload": base64_mulaw}
            )
            await self.websocket.send_text(outbound_msg.json())
        except WebSocketDisconnect:
            logger.warning("WebSocket disconnected while trying to send audio to Twilio.")
            self.is_active = False
        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {e}", exc_info=True)

    async def _handle_gemini_text_response(self, text: str):
        try:
            call_id_info = self.call_session.call_sid if self.call_session else 'N/A'
            logger.info(f"Received text from Gemini for call {call_id_info}: {text}")
        except Exception as e:
            logger.error(f"Error handling Gemini text response: {e}", exc_info=True)

    async def _handle_stream_stop(self, msg: TwilioMediaMessage):
        try:
            logger.info(f"Media stream stopped: {self.stream_sid}")
            self.is_active = False # Mark handler as inactive first
            if self._user_speech_timer:
                self._user_speech_timer.cancel()
            if self.gemini_client:
                await self.gemini_client.stop_session()
        except Exception as e:
            logger.error(f"Error handling stream stop: {e}", exc_info=True)

    async def _cleanup(self):
        logger.info(f"Cleaning up WebSocket connection for stream: {self.stream_sid or 'N/A'}")
        self.is_active = False # Ensure inactive
        if self._user_speech_timer:
            self._user_speech_timer.cancel()
            self._user_speech_timer = None

        if self.gemini_client:
            await self.gemini_client.stop_session()
            self.gemini_client = None
        
        if self.call_session and self.call_session.call_sid in active_sessions:
            try:
                del active_sessions[self.call_session.call_sid]
                logger.debug(f"Removed session {self.call_session.call_sid} from active_sessions.")
            except KeyError:
                logger.warning(f"Session {self.call_session.call_sid} already removed or not found in active_sessions.")
        
        # Ensure WebSocket is closed if not already
        if self.websocket and self.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await self.websocket.close()
                logger.debug("WebSocket closed during cleanup.")
            except Exception as e:
                logger.error(f"Error closing WebSocket during cleanup: {e}", exc_info=True)
        logger.info(f"Cleaned up WebSocket connection for stream: {self.stream_sid or 'N/A'} - completed.")


async def handle_media_stream(websocket: WebSocket):
    handler = TwilioMediaStreamHandler(websocket)
    await handler.handle_connection()

```

---

## 3. Mermaid Diagram (Updated Flow)

```mermaid
sequenceDiagram
    participant Twilio
    participant WebSocketHandler as app.twilio_integration.websockets.TwilioMediaStreamHandler
    participant GeminiClient as app.gemini_integration.streaming.GeminiStreamingClient
    participant GeminiLiveAPI as Google Gemini Live API

    Twilio->>+WebSocketHandler: WebSocket Connect (Media Stream Start Event)
    WebSocketHandler->>WebSocketHandler: _handle_stream_start()
    WebSocketHandler->>+GeminiClient: __init__()
    WebSocketHandler->>GeminiClient: set_callbacks(audio_cb, text_cb)
    WebSocketHandler->>GeminiClient: start_session(initial_prompt)
    activate GeminiClient
    GeminiClient->>+GeminiLiveAPI: Connect (model, config)
    GeminiLiveAPI-->>-GeminiClient: Session Established
    GeminiClient->>GeminiLiveAPI: Send initial_prompt (text, end_of_turn=True)
    Note over GeminiClient: Starts internal _send_loop & _receive_loop
    GeminiClient-->>WebSocketHandler: Session Started (returns)
    deactivate GeminiClient

    loop Twilio Media Stream Active
        Twilio->>WebSocketHandler: Media Message (audio_payload from user)
        WebSocketHandler->>WebSocketHandler: _handle_media_message()
        WebSocketHandler->>WebSocketHandler: process_twilio_to_gemini(audio_payload)
        WebSocketHandler->>GeminiClient: send_audio_chunk(pcm_audio_chunk)
        GeminiClient->>GeminiClient: _audio_send_queue.put(pcm_audio_chunk)
        
        %% Simplified: VAD / end_of_turn logic
        %% WebSocketHandler->>GeminiClient: signal_end_of_user_turn() [Based on VAD or timer]
        %% GeminiClient->>GeminiClient: _text_send_queue.put({content:"", end_of_turn:True})

        Note right of GeminiClient: _send_loop picks from queues & sends to LiveAPI
        %% Example: GeminiClient sends audio_chunk (end_of_turn=False)
        %% Example: GeminiClient sends end_of_turn signal (end_of_turn=True)

        Note right of GeminiClient: _receive_loop listens for responses
        GeminiLiveAPI-->>GeminiClient: Response (contains audio_data / text_data / error)
        alt Audio Response from Gemini
            GeminiClient->>WebSocketHandler: audio_output_callback(audio_data_from_gemini)
            WebSocketHandler->>WebSocketHandler: process_gemini_to_twilio(audio_data)
            WebSocketHandler->>Twilio: Media Message (audio_payload to user)
        else Text Response from Gemini
            GeminiClient->>WebSocketHandler: text_output_callback(text_from_gemini)
            WebSocketHandler->>WebSocketHandler: Log text (or other action)
        else Error Response from Gemini
            GeminiClient->>WebSocketHandler: (Logs error, may stop session)
        end
    end

    Twilio->>WebSocketHandler: Stop Message / WebSocket Disconnect
    WebSocketHandler->>WebSocketHandler: _handle_stream_stop() or _cleanup()
    WebSocketHandler->>+GeminiClient: stop_session()
    activate GeminiClient
    GeminiClient->>GeminiClient: Cancel _send_loop, _receive_loop
    GeminiClient->>GeminiLiveAPI: (Session closes implicitly or by server)
    GeminiLiveAPI-->>-GeminiClient: (Session Closed)
    GeminiClient-->>WebSocketHandler: Session Stopped (returns)
    deactivate GeminiClient
    WebSocketHandler-->>-Twilio: WebSocket Close
```

---

This plan provides a comprehensive approach to integrating the Gemini Live API. The `signal_end_of_user_turn()` logic in `TwilioMediaStreamHandler` remains a key point for refinement during actual implementation to achieve natural turn-taking.