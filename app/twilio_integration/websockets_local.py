"""WebSocket handler for Twilio media stream processing."""

import json
import logging
import asyncio
import time
import wave
import audioop
import base64
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState # ADDED IMPORT
from app.config import settings
from app.core.models import TwilioMediaMessage, TwilioOutboundMedia, CallSession
from app.audio_processing.utils import audio_processor

logger = logging.getLogger(__name__)

# Global dictionary to track active call sessions
active_sessions: Dict[str, CallSession] = {}


class TwilioMediaStreamHandler:
    """Handles Twilio media stream WebSocket connections."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.call_session: Optional[CallSession] = None
        self.stream_sid: Optional[str] = None
        self.is_active = False
        
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
            
            # Start playing the sample audio file
            if self.is_active:
                logger.info(f"Initiating sample audio playback for call: {call_sid}")
                asyncio.create_task(self._play_sample_audio())
            else:
                logger.warning("WebSocket connection became inactive before sample audio playback could start.")
            
            logger.info(f"Stream start handled for call: {call_sid}")

        except Exception as e:
            logger.error(f"Error handling stream start: {e}", exc_info=True)

    async def _handle_media_message(self, msg: TwilioMediaMessage):
        """Handle incoming audio media from Twilio.
        
        Args:
            msg: Twilio media message containing audio data
        """
        try:
            if not msg.media:
                return

            audio_payload = msg.media.get('payload')
            if not audio_payload:
                return
            
            # Log incoming media for debugging purposes
            logger.debug(f"Received media message with payload length: {len(audio_payload)}")

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
        except Exception as e:
            logger.error(f"Error handling stream stop: {e}", exc_info=True)

    async def _send_audio_to_twilio(self, audio_data: bytes):
        """Send audio data to Twilio with proper mark messages.
        
        This is called when we have audio to send to Twilio.
        Uses either queue-based or immediate delivery based on configuration.
        
        Args:
            audio_data: PCM audio data (typically 24kHz)
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
            audio_data: PCM audio data (typically 24kHz)
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
            audio_data: PCM audio data (typically 24kHz)
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
                        logger.info(f"DEBUG: Audio sender loop - send text - {message[:100]}")
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

    async def _play_sample_audio(self):
        """Load and play the sample audio file in 100ms chunks."""
        try:
            wav_path = "sample_audio/output.wav"  # Relative to project root
            logger.info(f"Starting playback of sample audio: {wav_path}")

            # First, try to open with wave module to get basic info
            try:
                with wave.open(wav_path, 'rb') as wf:
                    source_wav_rate = wf.getframerate()
                    source_wav_channels = wf.getnchannels()
                    num_frames = wf.getnframes()
                    logger.info(f"WAV file info: {source_wav_rate}Hz, {source_wav_channels} channels, {num_frames} frames")
                    
                    # Calculate bytes to read for 100ms chunk at 8kHz μ-law (1 byte per sample)
                    bytes_per_100ms_chunk = int(source_wav_rate * 0.100)  # 0.100 seconds = 100ms
                    
                    total_frames_read = 0
                    chunk_count = 0
                    while total_frames_read < num_frames:
                        if not self.is_active:
                            logger.info("Stopping sample audio playback as handler is no longer active.")
                            break

                        frames_to_read = min(bytes_per_100ms_chunk, num_frames - total_frames_read)
                        raw_frames = wf.readframes(frames_to_read)
                        total_frames_read += frames_to_read

                        if not raw_frames:  # End of file or error
                            break

                        # Since this is already μ-law at 8kHz mono, we can send it directly
                        await self._send_mulaw_to_twilio(raw_frames)
                        chunk_count += 1
                        logger.debug(f"Queued chunk {chunk_count}: {len(raw_frames)} bytes of μ-law audio for Twilio.")
                        
                        # Yield control to allow other tasks to run, including the audio sender.
                        await asyncio.sleep(0.01)

                    logger.info(f"Finished processing and queueing sample audio: {wav_path} ({chunk_count} chunks)")
                    
            except wave.Error as e:
                if "unknown format" in str(e):
                    logger.info(f"WAV file appears to be μ-law format, reading as raw binary: {e}")
                    # Read the file as raw binary and skip the WAV header
                    await self._play_raw_mulaw_audio(wav_path)
                else:
                    raise

        except FileNotFoundError:
            logger.error(f"Sample audio file not found: {wav_path}")
        except Exception as e:
            logger.error(f"Error in _play_sample_audio: {e}", exc_info=True)

    async def _play_raw_mulaw_audio(self, wav_path: str):
        """Play μ-law audio by reading raw binary data and skipping WAV header (first 10 seconds only)."""
        try:
            with open(wav_path, 'rb') as f:
                # Skip WAV header (typically 44 bytes for standard WAV)
                # We'll read the header to find the data chunk
                header = f.read(44)
                if len(header) < 44:
                    logger.error("File too small to contain valid WAV header")
                    return
                
                # Find the data chunk (this is a simplified approach)
                # For μ-law files created by ffmpeg, the data usually starts at byte 44
                audio_data = f.read()
                
                if not audio_data:
                    logger.error("No audio data found in file")
                    return
                
                # Limit to first 10 seconds (8kHz mono μ-law = 8000 bytes per second)
                max_bytes = 8000 * 10  # 80,000 bytes for 10 seconds
                if len(audio_data) > max_bytes:
                    audio_data = audio_data[:max_bytes]
                    logger.info(f"Limiting audio to first 10 seconds: {len(audio_data)} bytes")
                else:
                    logger.info(f"Reading raw μ-law data: {len(audio_data)} bytes")
                
                # Calculate bytes for 100ms chunks at 8kHz (800 bytes for 100ms)
                bytes_per_100ms = 800  # 8000 Hz * 0.1 seconds * 1 byte per sample
                
                chunk_count = 0
                offset = 0
                while offset < len(audio_data):
                    if not self.is_active:
                        logger.info("Stopping sample audio playback as handler is no longer active.")
                        break
                    
                    chunk_size = min(bytes_per_100ms, len(audio_data) - offset)
                    chunk = audio_data[offset:offset + chunk_size]
                    offset += chunk_size
                    
                    if not chunk:
                        break
                    
                    await self._send_mulaw_to_twilio(chunk)
                    chunk_count += 1
                    logger.info(f"Queued raw chunk {chunk_count}: {len(chunk)} bytes of μ-law audio for Twilio.")
                    
                    # Yield control to allow other tasks to run
                    await asyncio.sleep(0.01)
                
                logger.info(f"Finished processing raw μ-law audio: {wav_path} ({chunk_count} chunks)")
                
        except Exception as e:
            logger.error(f"Error reading raw μ-law audio: {e}", exc_info=True)

    async def _send_mulaw_to_twilio(self, mulaw_data: bytes):
        """Send μ-law audio data directly to Twilio (bypassing PCM conversion)."""
        try:
            if not self.is_active or not self.stream_sid:
                logger.warning("Cannot send audio to Twilio: Handler not active or stream_sid missing.")
                return

            # Convert μ-law bytes directly to base64 for Twilio
            base64_mulaw = base64.b64encode(mulaw_data).decode('utf-8')
            
            # Generate unique chunk ID for mark message synchronization
            chunk_id = f"mulaw_chunk_{int(time.time() * 1000)}_{len(mulaw_data)}"
            
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
            
            logger.debug(f"SUCCESS: μ-law audio and mark messages queued for Twilio (chunk: {chunk_id})")
            
        except Exception as e:
            logger.error(f"Error sending μ-law audio to Twilio: {e}", exc_info=True)

    async def _cleanup(self):
        logger.info(f"Cleaning up WebSocket connection for stream: {self.stream_sid or 'N/A'}")
        self.is_active = False # Ensure inactive

        # Wait for audio queue to be empty before cancelling the sender task
        if self._audio_sender_task and not self._audio_sender_task.done():
            try:
                # Wait for the queue to be processed (with timeout to avoid hanging)
                queue_empty_timeout = 6.0  # 6 seconds timeout
                start_time = asyncio.get_event_loop().time()
                
                while not self._audio_queue.empty():
                    if asyncio.get_event_loop().time() - start_time > queue_empty_timeout:
                        logger.warning(f"Audio queue not empty after {queue_empty_timeout}s timeout, proceeding with cleanup")
                        break
                    await asyncio.sleep(0.1)  # Check every 100ms
                
                if self._audio_queue.empty():
                    logger.info("Audio queue is empty, proceeding with sender task cleanup")
                else:
                    logger.warning(f"Audio queue still has {self._audio_queue.qsize()} items, proceeding with cleanup anyway")
                    
            except Exception as e:
                logger.error(f"Error waiting for audio queue to empty: {e}")

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