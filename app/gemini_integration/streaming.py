# app/gemini_integration/streaming.py
import asyncio
import logging
from google import genai
from google.genai import types
from google.genai.types import ( # ADDED IMPORTS
    LiveConnectConfig,
    Content,
    Part,
    SpeechConfig,
    VoiceConfig,
    PrebuiltVoiceConfig,
    LiveClientRealtimeInput,
    Blob
)
# from google.generativeai.types import LiveSession # Check actual import if needed for type hints
from app.config import settings
from typing import Callable, Optional
from collections.abc import Awaitable # ADDED IMPORT

# Configure basic logging (ensure LOG_LEVEL is in settings or handle absence)
log_level_setting = getattr(settings, 'LOG_LEVEL', 'INFO') # Safely get LOG_LEVEL
logging.basicConfig(level=log_level_setting.upper())
logger = logging.getLogger(__name__)

class GeminiStreamingClient:
    def __init__(self, model_name: str = settings.gemini_model):
        self.model_name = model_name
        self.live_session: Optional[genai.live.AsyncLiveSession] = None # Type hint for AsyncLiveSession
        self._session_context_manager = None # ADDED
        self.is_active = False
        self.client = None
        self._audio_send_queue = asyncio.Queue()
        # REMOVED: _text_send_queue - audio-only phone calls don't need text
        self._receive_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None
        self._audio_output_callback: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._text_output_callback: Optional[Callable[[str], Awaitable[None]]] = None

        if not settings.google_cloud_project:
            logger.error("GOOGLE_CLOUD_PROJECT not found in settings.")
            raise ValueError("GOOGLE_CLOUD_PROJECT must be configured for Vertex AI.")

        try:
            # DIAGNOSTIC: Log configuration details
            logger.info(f"Initializing Gemini Client with Vertex AI:")
            logger.info(f"  - Project: {settings.google_cloud_project}")
            logger.info(f"  - Location: {settings.google_cloud_location}")
            logger.info(f"  - API Version: {settings.gemini_api_version}")
            logger.info(f"  - Model: {self.model_name}")
            logger.info(f"  - Credentials: {settings.google_application_credentials}")
            
            self.client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location
            )
            logger.info(f"Gemini Client initialized for Live API version '{settings.gemini_api_version}' with Vertex AI.")
        except Exception as e:
            logger.exception(f"Failed to initialize Gemini Client: {e}")
            raise

    def set_callbacks(self,
                      audio_callback: Callable[[bytes], Awaitable[None]],
                      text_callback: Callable[[str], Awaitable[None]]):
        self._audio_output_callback = audio_callback
        self._text_output_callback = text_callback

    async def start_session(self, initial_prompt: str = settings.system_prompt):
        if self.is_active:
            logger.warning("Session already active.")
            return

        logger.info(f"Starting Gemini Live API session with model '{self.model_name}'.")
        try:
            # Use configuration that matches the working diagnostic script
            live_connect_config_args = {
                "response_modalities": ["AUDIO"]  # Only AUDIO, not TEXT
            }
            # Always include speech config with default voice
            live_connect_config_args["speech_config"] = SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(
                        voice_name=settings.gemini_voice_name or "Puck"
                    )
                )
            )
            
            # DIAGNOSTIC: Log session configuration
            logger.info(f"Live API session configuration:")
            logger.info(f"  - Model: {self.model_name}")
            logger.info(f"  - Response modalities: {live_connect_config_args['response_modalities']}")
            logger.info(f"  - Voice name: {settings.gemini_voice_name}")
            logger.info(f"  - Client type: {type(self.client)}")
            
            session_config = LiveConnectConfig(**live_connect_config_args)

            self._session_context_manager = self.client.aio.live.connect(
                model=self.model_name,
                config=session_config
            )
            
            logger.info("Attempting to establish WebSocket connection...")
            self.live_session = await self._session_context_manager.__aenter__() # MODIFIED
            logger.info(f"Gemini Live API session connected.")

            if initial_prompt:
                logger.info(f"Sending initial prompt to Gemini Live API: '{initial_prompt}'")
                # Send initial prompt using the correct API method
                await self.live_session.send(input=initial_prompt, end_of_turn=True)
                logger.info("Initial prompt sending temporarily disabled - connection test successful!")

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
        logger.info("Gemini send loop started.")
        try:
            while self.is_active and self.live_session:
                # AUDIO-ONLY: Only process audio chunks for phone calls
                try:
                    audio_chunk_item = self._audio_send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.01) # Small pause if both queues are empty
                    continue
                
                if audio_chunk_item:
                    # Convert raw bytes to proper Gemini Live API format
                    logger.info(f"🔊 Sending audio chunk: {len(audio_chunk_item)} bytes")
                    
                    # Create proper LiveClientRealtimeInput with media_chunks
                    audio_input = LiveClientRealtimeInput(
                        media_chunks=[
                            Blob(
                                mime_type="audio/pcm",  # 16-bit PCM audio
                                data=audio_chunk_item
                            )
                        ]
                    )
                    
                    try:
                        await self.live_session.send(input=audio_input)
                        logger.debug("✅ Audio chunk sent successfully")
                    except Exception as audio_error:
                        logger.error(f"❌ Audio sending failed: {audio_error}")
                        raise
                    
                    self._audio_send_queue.task_done()
                    
        except asyncio.CancelledError:
            logger.info("Gemini send loop cancelled.")
        except Exception as e:
            logger.exception(f"Error in Gemini send loop: {e}")
            self.is_active = False 
        finally:
            logger.info("Gemini send loop finished.")

    async def _receive_loop(self):
        logger.info("Gemini receive loop started.")
        try:
            if not self.live_session:
                logger.error("Receive loop started without an active session.")
                return

            async for response in self.live_session.receive():
                if not self.is_active: break

                # Check for audio data
                if response.server_content and response.server_content.model_turn and response.server_content.model_turn.parts:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_data = part.inline_data.data
                            logger.info(f"Received audio data chunk of size {len(audio_data)} from Gemini.")
                            if self._audio_output_callback:
                                await self._audio_output_callback(audio_data)
                
                # Check for text data
                if response.text:
                    logger.info(f"Gemini text response: {response.text}")
                    if self._text_output_callback:
                        await self._text_output_callback(response.text)
                

                
                # Check for function call (not implemented yet, but good to be aware of)
                if response.tool_call:
                    logger.info(f"Received tool_call from Gemini: {response.tool_call}")

        except asyncio.CancelledError:
            logger.info("Gemini receive loop cancelled.")
        except Exception as e:
            logger.exception(f"Error in Gemini receive loop: {e}")
            self.is_active = False
        finally:
            logger.info("Gemini receive loop finished.")

    async def send_audio_chunk(self, audio_chunk: bytes):
        if not self.is_active:
            # logger.warning("Session not active. Cannot send audio.")
            return
        await self._audio_send_queue.put(audio_chunk)

    async def signal_end_of_user_turn(self):
        if not self.is_active:
            logger.warning("Session not active. Cannot signal end of turn.")
            return
        
        # AUDIO-ONLY: For phone calls, turn signaling should be handled by the Gemini Live API
        # automatically based on audio silence detection (Voice Activity Detection)
        logger.info("🔊 Audio-only mode: Turn signaling handled automatically by Gemini Live API VAD")
        # No explicit turn signaling needed - the API detects silence automatically

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
            except asyncio.CancelledError: logger.info("Send task confirmed cancelled.")
        if self._receive_task:
            try: await self._receive_task
            except asyncio.CancelledError: logger.info("Receive task confirmed cancelled.")
        
        if self._session_context_manager: # ADDED BLOCK
            try:
                logger.info("Exiting session context manager.")
                await self._session_context_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error during session context manager __aexit__: {e}")
            finally:
                self._session_context_manager = None
        
        self.live_session = None
        
        # Clear audio queue (text queue removed for audio-only mode)
        while not self._audio_send_queue.empty():
            try: self._audio_send_queue.get_nowait(); self._audio_send_queue.task_done()
            except asyncio.QueueEmpty: break

        logger.info("Gemini Live API session stopped and cleaned up.")