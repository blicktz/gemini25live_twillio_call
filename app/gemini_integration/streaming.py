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
    PrebuiltVoiceConfig
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
        self._text_send_queue = asyncio.Queue() # For sending explicit text or end-of-turn signals
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
                location=settings.google_cloud_location,
                http_options=types.HttpOptions(api_version=settings.gemini_api_version)
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
            live_connect_config_args = {
                "response_modalities": ["AUDIO", "TEXT"]
            }
            if settings.gemini_voice_name:
                live_connect_config_args["speech_config"] = SpeechConfig(
                    voice_config=VoiceConfig(
                        prebuilt_voice_config=PrebuiltVoiceConfig(
                            voice_name=settings.gemini_voice_name
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
                await self.live_session.send_client_content(
                    turns=Content(role="user", parts=[Part(text=initial_prompt)])
                )

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
                text_message_item = None
                audio_chunk_item = None
                
                try: # Check for text message first
                    text_message_item = self._text_send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

                if text_message_item:
                    text_content = text_message_item['content']
                    # end_of_turn is implicitly handled by how send_client_content structures turns.
                    # For an explicit end-of-turn signal with empty content, this structure is appropriate.
                    logger.info(f"Sending text to Gemini via send_client_content: '{text_content[:50]}...'")
                    await self.live_session.send_client_content(
                        turns=Content(role="user", parts=[Part(text=text_content)])
                    )
                    self._text_send_queue.task_done()
                    continue

                try: # Then check for audio chunk
                    audio_chunk_item = self._audio_send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.01) # Small pause if both queues are empty
                    continue
                
                if audio_chunk_item:
                    # logger.info(f"Sending audio chunk of size {len(audio_chunk_item)} bytes to Gemini.")
                    await self.live_session.send(input=audio_chunk_item, end_of_turn=False)
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
                
                # Check for errors
                if response.error: # Assuming error is a top-level attribute in the response object
                    logger.error(f"Gemini Live API error in response: {response.error}")
                    self.is_active = False # Stop on error
                    break
                
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
        logger.info("Signaling end of user turn to Gemini.")
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
        
        # Clear queues
        while not self._audio_send_queue.empty():
            try: self._audio_send_queue.get_nowait(); self._audio_send_queue.task_done()
            except asyncio.QueueEmpty: break
        while not self._text_send_queue.empty():
            try: self._text_send_queue.get_nowait(); self._text_send_queue.task_done()
            except asyncio.QueueEmpty: break

        logger.info("Gemini Live API session stopped and cleaned up.")