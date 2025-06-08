"""WebSocket handler for Twilio media stream processing."""

import json
import logging
import asyncio
import time
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState # ADDED IMPORT
from app.config import settings
from app.core.models import TwilioMediaMessage, TwilioOutboundMedia, CallSession
from app.audio_processing.utils import audio_processor
from app.gemini_integration.streaming import GeminiStreamingClient

logger = logging.getLogger(__name__)

# Global dictionary to track active call sessions
active_sessions: Dict[str, CallSession] = {}


class TwilioMediaStreamHandler:
    """Handles Twilio media stream WebSocket connections."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.call_session: Optional[CallSession] = None
        self.gemini_client: Optional[GeminiStreamingClient] = None
        self.stream_sid: Optional[str] = None
        self.is_active = False
        # TODO: Add a timer or mechanism to detect end of user speech for signal_end_of_user_turn
        self._user_speech_timer: Optional[asyncio.TimerHandle] = None
        self._silence_threshold_sec = 1.0 # Example: 1 second of silence
        
        # Audio queue system for proper Twilio audio delivery
        self._audio_queue: asyncio.Queue[str] = asyncio.Queue()
        self._audio_sender_task: Optional[asyncio.Task] = None
        self._use_audio_queue = getattr(settings, 'use_twilio_audio_queue', True)

    async def handle_connection(self):
        """Handle the WebSocket connection lifecycle."""
        try:
            await self.websocket.accept()
            logger.info("WebSocket connection accepted")
            
            self.is_active = True
            
            # Start audio sender task for queue-based audio delivery
            self._audio_sender_task = asyncio.create_task(self._audio_sender_loop())
            
            # Start listening for messages
            await self._listen_for_messages()
            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _listen_for_messages(self):
        """Listen for incoming WebSocket messages from Twilio."""
        while self.is_active:
            try:
                # Receive message from Twilio
                message = await self.websocket.receive_text()
                await self._process_message(message)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during message listening")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                break # Stop listening on error
    
    async def _process_message(self, message: str):
        """Process incoming message from Twilio.
        
        Args:
            message: JSON string message from Twilio
        """
        try:
            # Parse JSON message
            data = json.loads(message)
            msg = TwilioMediaMessage(**data)
            
            if msg.event == "start":
                await self._handle_stream_start(msg)
            elif msg.event == "media":
                await self._handle_media_message(msg)
            elif msg.event == "stop":
                await self._handle_stream_stop(msg)
            elif msg.event == "mark":
                # Handle mark acknowledgment from Twilio

                mark_name = msg.mark.get('name', 'unknown') if isinstance(msg.mark, dict) else getattr(msg.mark, 'name', 'unknown')
                logger.info(f"Twilio acknowledged audio chunk: {mark_name}")
                # Check for special VAD marks
                if mark_name == "user_finished_speaking":
                    if self.gemini_client and self.gemini_client.is_active:
                        await self.gemini_client.signal_end_of_user_turn()

            else:
                logger.info(f"Received unknown event: {msg.event}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def _handle_stream_start(self, msg: TwilioMediaMessage):
        """Handle stream start event from Twilio.
        
        Args:
            msg: Twilio media message containing start information
        """
        try:
            start_data = msg.start
            if not start_data:
                logger.error("No start data in stream start message")
                return
            
            self.stream_sid = start_data.get('streamSid')
            call_sid = start_data.get('callSid')
            
            logger.info(f"Media stream started: {self.stream_sid} for call: {call_sid}")
            
            # Create call session
            self.call_session = CallSession(
                call_sid=call_sid,
                stream_sid=self.stream_sid,
                is_active=True
            )
            
            # Store in global sessions
            if call_sid:
                active_sessions[call_sid] = self.call_session
            
            # Initialize Gemini streaming client (ADK-based)
            self.gemini_client = GeminiStreamingClient()
            self.gemini_client.set_callbacks(
                audio_callback=self._send_audio_to_twilio,
                text_callback=self._handle_gemini_text_response
            )
            # ADK-based client uses session_id instead of initial_prompt
            # The system prompt is configured in the root_agent
            await self.gemini_client.start_session(session_id=call_sid or self.stream_sid)
            logger.info(f"ADK-based Gemini session started for call: {call_sid}")

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
        """Handle incoming audio media from Twilio.
        
        Args:
            msg: Twilio media message containing audio data
        """
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

            # NOT USED 
            # For simplicity, let's signal end of turn after each chunk for now.
            # This is not ideal for natural conversation but ensures Gemini responds.
            # A better VAD or mark-based system is needed for production.
            #await self.gemini_client.signal_end_of_user_turn()


        except Exception as e:
            logger.error(f"Error handling media message: {e}", exc_info=True)

    async def _handle_stream_stop(self, msg: TwilioMediaMessage):
        """Handle stream stop event from Twilio.
        
        Args:
            msg: Twilio media message containing stop information
        """
        try:
            logger.info(f"Media stream stopped: {self.stream_sid}")
            self.is_active = False # Mark handler as inactive first
            if self._user_speech_timer:
                self._user_speech_timer.cancel()
            if self.gemini_client:
                await self.gemini_client.stop_session()
        except Exception as e:
            logger.error(f"Error handling stream stop: {e}", exc_info=True)

    async def _send_audio_to_twilio(self, audio_data: bytes):
        """Send audio data to Twilio with proper mark messages.
        
        This is called by the Gemini client when it has audio to send.
        Uses either queue-based or immediate delivery based on configuration.
        
        Args:
            audio_data: PCM audio data from Gemini (typically 24kHz)
        """
        try:
            logger.info(f"DEBUG: _send_audio_to_twilio called with {len(audio_data)} bytes")
            logger.info(f"DEBUG: is_active={self.is_active}, stream_sid={self.stream_sid}")
            
            if not self.is_active or not self.stream_sid:
                logger.warning("Cannot send audio to Twilio: Handler not active or stream_sid missing.")
                return

            # Choose delivery method based on configuration
            if self._use_audio_queue:
                await self._queue_audio_for_twilio(audio_data)
            else:
                await self._send_audio_immediate(audio_data)
            
        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {e}", exc_info=True)

    async def _queue_audio_for_twilio(self, audio_data: bytes):
        """Queue audio data for sending to Twilio with proper mark messages.
        
        Args:
            audio_data: PCM audio data from Gemini (typically 24kHz)
        """
        try:
            logger.info("Processing audio for Twilio (queue method)...")

            # Process audio to Twilio format
            base64_mulaw = audio_processor.process_gemini_to_twilio(
                audio_data,
                input_rate=settings.gemini_output_sample_rate,
                output_rate=settings.output_sample_rate,
                save_debug_audio=settings.save_debug_audio
            )
            
            logger.debug(f"DEBUG: Processed audio - base64_mulaw length: {len(base64_mulaw)}")
            
            # Generate unique chunk ID for mark message synchronization
            chunk_id = f"chunk_{int(time.time() * 1000)}_{len(audio_data)}"
            
            # Create media message
            media_message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64_mulaw}
            }
            
            # Create mark message for synchronization
            mark_message = {
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": chunk_id}
            }
            
            # Queue both messages for delivery
            self._audio_queue.put_nowait(json.dumps(media_message))
            self._audio_queue.put_nowait(json.dumps(mark_message))
            
            logger.info(f"SUCCESS: Audio and mark messages queued for Twilio (chunk: {chunk_id})")
            
        except Exception as e:
            logger.error(f"Error queuing audio for Twilio: {e}", exc_info=True)

    async def _send_audio_immediate(self, audio_data: bytes):
        """Send audio data immediately to Twilio with proper mark messages.
        
        This method bypasses the queue system and sends audio directly.
        
        Args:
            audio_data: PCM audio data from Gemini (typically 24kHz)
        """
        try:
            if not self.is_active or not self.stream_sid or \
               not self.websocket or self.websocket.client_state != WebSocketState.CONNECTED:
                logger.warning("Cannot send audio to Twilio: WebSocket not active/connected or stream_sid missing.")
                return

            logger.info("Processing audio for Twilio (immediate method)...")

            # Process audio to Twilio format
            base64_mulaw = audio_processor.process_gemini_to_twilio(
                audio_data,
                input_rate=settings.gemini_output_sample_rate,
                output_rate=settings.output_sample_rate,
                save_debug_audio=settings.save_debug_audio
            )
            
            logger.info(f"DEBUG: Processed audio - base64_mulaw length: {len(base64_mulaw)}")
            
            # Generate unique chunk ID
            chunk_id = f"immediate_{int(time.time() * 1000)}_{len(audio_data)}"
            
            # Send media message
            media_message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64_mulaw}
            }
            await self.websocket.send_text(json.dumps(media_message))
            
            # Send mark message immediately after
            mark_message = {
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": chunk_id}
            }
            await self.websocket.send_text(json.dumps(mark_message))
            
            logger.info(f"SUCCESS: Audio and mark messages sent immediately to Twilio (chunk: {chunk_id})")
            
        except WebSocketDisconnect:
            logger.warning("WebSocket disconnected while trying to send audio to Twilio.")
            self.is_active = False
        except Exception as e:
            logger.error(f"Error sending audio immediately to Twilio: {e}", exc_info=True)

    async def _audio_sender_loop(self):
        """Dedicated loop for sending audio messages to Twilio.
        
        This loop runs continuously while the handler is active,
        processing messages from the audio queue and sending them to Twilio.
        """
        try:
            logger.info("Audio queue system enabled for Twilio delivery")
            while self.is_active:
                try:
                    # Wait for a message in the queue
                    message = await self._audio_queue.get()
                    
                    # Check if WebSocket is still connected
                    if self.websocket and self.websocket.client_state == WebSocketState.CONNECTED:
                        logger.debug(f"DEBUG: Audio sender loop - send text - {message}")
                        await self.websocket.send_text(message)
                    else:
                        logger.warning("WebSocket not connected, dropping audio message")
                        
                    # Mark task as done
                    self._audio_queue.task_done()
                    
                except asyncio.CancelledError:
                    logger.info("Audio sender loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in audio sender loop: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Fatal error in audio sender loop: {e}", exc_info=True)
        finally:
            logger.info("Audio sender loop stopped")

    async def _handle_gemini_text_response(self, text: str):
        try:
            call_id_info = self.call_session.call_sid if self.call_session else 'N/A'
            logger.info(f"Received text from Gemini for call {call_id_info}: {text}")
        except Exception as e:
            logger.error(f"Error handling Gemini text response: {e}", exc_info=True)

    async def _cleanup(self):
        logger.info(f"Cleaning up WebSocket connection for stream: {self.stream_sid or 'N/A'}")
        self.is_active = False # Ensure inactive
        
        # Cancel user speech timer
        if self._user_speech_timer:
            self._user_speech_timer.cancel()
            self._user_speech_timer = None

        # Cancel and cleanup audio sender task
        if self._audio_sender_task:
            self._audio_sender_task.cancel()
            try:
                await self._audio_sender_task
            except asyncio.CancelledError:
                logger.info("Audio sender task cancelled successfully")
            except Exception as e:
                logger.error(f"Error cancelling audio sender task: {e}")
            self._audio_sender_task = None

        # Clear any remaining items in the audio queue
        try:
            while not self._audio_queue.empty():
                self._audio_queue.get_nowait()
            logger.info("Audio queue cleared")
        except Exception as e:
            logger.error(f"Error clearing audio queue: {e}")

        # Stop Gemini client
        if self.gemini_client:
            await self.gemini_client.stop_session()
            self.gemini_client = None
        
        # Remove from active sessions
        if self.call_session and self.call_session.call_sid in active_sessions:
            try:
                del active_sessions[self.call_session.call_sid]
                logger.info(f"Removed session {self.call_session.call_sid} from active_sessions.")
            except KeyError:
                logger.warning(f"Session {self.call_session.call_sid} already removed or not found in active_sessions.")
        
        # Ensure WebSocket is closed if not already
        if self.websocket and self.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await self.websocket.close()
                logger.info("WebSocket closed during cleanup.")
            except Exception as e:
                logger.error(f"Error closing WebSocket during cleanup: {e}", exc_info=True)
        logger.info(f"Cleaned up WebSocket connection for stream: {self.stream_sid or 'N/A'} - completed.")


async def handle_media_stream(websocket: WebSocket):
    """FastAPI WebSocket endpoint handler for Twilio media streams.
    
    Args:
        websocket: FastAPI WebSocket connection
    """
    handler = TwilioMediaStreamHandler(websocket)
    await handler.handle_connection()