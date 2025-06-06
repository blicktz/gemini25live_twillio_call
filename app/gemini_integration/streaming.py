# app/gemini_integration/streaming.py
import asyncio
import logging
from google import generativeai as genai
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
        self.is_active = False
        self.client = None
        self._audio_send_queue = asyncio.Queue()
        self._text_send_queue = asyncio.Queue() # For sending explicit text or end-of-turn signals
        self._receive_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None
        self._audio_output_callback: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._text_output_callback: Optional[Callable[[str], Awaitable[None]]] = None

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
                    content = text_message_item['content']
                    eot = text_message_item['end_of_turn']
                    logger.info(f"Sending text to Gemini: '{content[:50]}...', end_of_turn: {eot}")
                    await self.live_session.send(input=content, end_of_turn=eot)
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

                if response.data:
                    logger.info(f"Received audio data chunk of size {len(response.data)} from Gemini.")
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