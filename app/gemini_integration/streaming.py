"""
Refactored GeminiStreamingClient using Google ADK for Twilio voice call integration.
Phase 1: Foundational ADK Setup with basic lifecycle management.
Phase 3: Audio sending to ADK implemented.
Updated to use Vertex AI authentication.
"""

import asyncio
import logging
import os
from typing import Callable, Optional
from collections.abc import Awaitable

# ADK imports
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types as genai_types
from google.genai.types import Modality

# Import the root agent
from app.gemini_integration.adk_agent import root_agent
from app.config import settings

# Configure logging
log_level_setting = getattr(settings, 'LOG_LEVEL', 'INFO')
logging.basicConfig(level=log_level_setting.upper())
logger = logging.getLogger(__name__)


class GeminiStreamingClient:
    """
    ADK-based streaming client for Twilio voice call integration.
    Phase 1: Foundational setup with basic lifecycle management.
    Phase 3: Audio sending to ADK implemented.
    """
    
    def __init__(self):
        """Initialize the ADK-based streaming client."""
        # Verify Vertex AI authentication setup
        self._verify_vertexai_auth()
        
        # ADK Session Service
        self.session_service = InMemorySessionService()
        
        # Import and store root agent
        self.root_agent = root_agent
        
        # Application name for ADK
        self.APP_NAME = "TwilioGeminiADK"
        
        # Audio queue for incoming audio from Twilio
        self._audio_send_queue = asyncio.Queue()
        
        # ADK-specific attributes (initialized to None)
        self.live_request_queue: Optional[LiveRequestQueue] = None
        self.live_events = None
        self.adk_session = None
        self.runner: Optional[Runner] = None
        
        # Session state
        self.is_active = False
        
        # Async tasks for processing loops
        self._event_loop_task: Optional[asyncio.Task] = None
        self._send_loop_task: Optional[asyncio.Task] = None
        
        # Callbacks for audio and text output
        self._audio_output_callback: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._text_output_callback: Optional[Callable[[str], Awaitable[None]]] = None
        
        logger.info(f"GeminiStreamingClient initialized with ADK for app: {self.APP_NAME}")

    def _verify_vertexai_auth(self):
        """Verify that Vertex AI authentication is properly configured."""
        try:
            # Check required environment variables
            required_vars = [
                "GOOGLE_APPLICATION_CREDENTIALS",
                "GOOGLE_CLOUD_PROJECT",
                "GOOGLE_CLOUD_LOCATION"
            ]
            
            missing_vars = []
            for var in required_vars:
                if not os.environ.get(var):
                    missing_vars.append(var)
            
            if missing_vars:
                raise ValueError(f"Missing required environment variables for Vertex AI: {missing_vars}")
            
            # Check if credentials file exists
            creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if creds_path and not os.path.exists(creds_path):
                raise FileNotFoundError(f"Google Cloud credentials file not found: {creds_path}")
            
            # Log authentication configuration
            logger.info("Vertex AI authentication verified:")
            logger.info(f"  Project: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")
            logger.info(f"  Location: {os.environ.get('GOOGLE_CLOUD_LOCATION')}")
            logger.info(f"  Credentials: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
            logger.info(f"  Use Vertex AI: {os.environ.get('GOOGLE_GENAI_USE_VERTEXAI', 'False')}")
            
        except Exception as e:
            logger.error(f"Vertex AI authentication verification failed: {e}")
            raise

    def set_callbacks(self,
                      audio_callback: Callable[[bytes], Awaitable[None]],
                      text_callback: Callable[[str], Awaitable[None]]):
        """Set callbacks for audio and text output."""
        self._audio_output_callback = audio_callback
        self._text_output_callback = text_callback
        logger.info("Audio and text callbacks set")

    async def start_session(self, session_id: str):
        """
        Start an ADK session for the given session ID.
        Phase 1: Focus on ADK object creation and basic lifecycle management.
        """
        if self.is_active:
            logger.warning("Session already active.")
            return


        logger.info(f"Starting ADK session with ID: {session_id}")
        
        try:
            # Create ADK Session
            self.adk_session = await self.session_service.create_session(
                app_name=self.APP_NAME,
                user_id=session_id,
                session_id=session_id
            )
#            logger.info(f"ADK session created: {self.adk_session.session_id}")

            # Create Runner
            self.runner = Runner(
                app_name=self.APP_NAME,
                agent=self.root_agent,
                session_service=self.session_service
            )
            logger.info("ADK Runner created")

            # Define RunConfig with speech settings
            speech_config = genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=settings.gemini_voice_name or "Puck"
                    )
                )
            )
            
            run_config_dict = {
                "response_modalities": [Modality.AUDIO],
                "speech_config": speech_config,
                "output_audio_transcription": {},  # To get text logs of user speech
                "input_audio_transcription": {}   # Enable input audio transcription for VAD
            }
            run_config = RunConfig(**run_config_dict)
            logger.debug(f"DEBUG: RunConfig created with:")
            logger.info(f"  - Voice: {settings.gemini_voice_name or 'Puck'}")
            logger.info(f"  - Response modalities: {run_config_dict['response_modalities']}")
            logger.info(f"  - Speech config: {speech_config}")
            logger.info(f"  - Output audio transcription: {run_config_dict['output_audio_transcription']}")

            # Create LiveRequestQueue
            self.live_request_queue = LiveRequestQueue()
            logger.info("LiveRequestQueue created")

            # Start Live Run
            self.live_events = self.runner.run_live(
                session=self.adk_session,
                live_request_queue=self.live_request_queue,
                run_config=run_config
            )
            logger.info("ADK live run started")

            # Set session as active
            self.is_active = True

            # Create and start asyncio tasks for processing loops
            self._event_loop_task = asyncio.create_task(self._process_agent_events_loop())
            self._send_loop_task = asyncio.create_task(self._send_adk_loop())
            
            logger.info("ADK session started successfully with processing loops")

        except Exception as e:
            logger.exception(f"Failed to start ADK session: {e}")
            self.is_active = False
            # Clean up any partially created objects
            await self._cleanup_session_objects()
            raise

    async def stop_session(self):
        """
        Stop the ADK session and clean up resources.
        Phase 1: Focus on proper cleanup and task cancellation.
        """
        if not self.is_active:
            logger.info("ADK session already inactive.")
            return

        logger.info("Stopping ADK session")
        self.is_active = False

        # Close the live request queue if it exists
        if self.live_request_queue is not None:
            try:
                await self.live_request_queue.close()
                logger.info("LiveRequestQueue closed")
            except Exception as e:
                logger.error(f"Error closing LiveRequestQueue: {e}")

        # Cancel and wait for async tasks
        await self._cancel_and_wait_tasks()

        # Clean up session objects
        await self._cleanup_session_objects()

        # Clear audio queue
        self._clear_audio_queue()

        logger.info("ADK session stopped and cleaned up")

    async def _cancel_and_wait_tasks(self):
        """Cancel and wait for async tasks to complete."""
        tasks_to_cancel = []
        
        if self._event_loop_task and not self._event_loop_task.done():
            tasks_to_cancel.append(self._event_loop_task)
        
        if self._send_loop_task and not self._send_loop_task.done():
            tasks_to_cancel.append(self._send_loop_task)

        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} async tasks")
            for task in tasks_to_cancel:
                task.cancel()

            # Wait for tasks to complete cancellation
            for task in tasks_to_cancel:
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"Task {task.get_name()} cancelled successfully")
                except Exception as e:
                    logger.error(f"Error during task cancellation: {e}")

    async def _cleanup_session_objects(self):
        """Clean up ADK session objects."""
        # Note: InMemorySessionService might not have delete_session method
        # For now, we'll just clear local references
        if self.adk_session and self.session_service:
            try:
                # Try to delete session if method exists
                if hasattr(self.session_service, 'delete_session'):
                    self.session_service.delete_session(self.adk_session.session_id)
                    logger.info("ADK session deleted from session service")
            except Exception as e:
                logger.error(f"Error deleting session from service: {e}")

        # Reset ADK attributes to None
        self.live_request_queue = None
        self.live_events = None
        self.adk_session = None
        self.runner = None
        self._event_loop_task = None
        self._send_loop_task = None

    def _clear_audio_queue(self):
        """Clear the audio send queue."""
        while not self._audio_send_queue.empty():
            try:
                self._audio_send_queue.get_nowait()
                self._audio_send_queue.task_done()
            except asyncio.QueueEmpty:
                break
        logger.info("Audio send queue cleared")

    async def send_audio_chunk(self, audio_chunk: bytes):
        """
        Queue audio chunk for sending to ADK.
        Phase 3: Enhanced with validation and error handling.
        
        Args:
            audio_chunk: Raw audio data in 16kHz LPCM16 format from Twilio processing
        """
        if not self.is_active:
            logger.debug("Session not active, ignoring audio chunk")
            return
            
        if not audio_chunk:
            logger.debug("Empty audio chunk received, ignoring")
            return
            
        try:
            await self._audio_send_queue.put(audio_chunk)
            logger.debug(f"Queued audio chunk: {len(audio_chunk)} bytes")
        except Exception as e:
            logger.error(f"Failed to queue audio chunk: {e}")

    async def _send_adk_loop(self):
        """
        Process audio chunks from queue and send to ADK.
        Phase 3: Implement actual audio sending to ADK.
        """
        logger.info("ADK send loop started")
        try:
            while self.is_active:
                try:
                    # Get audio chunk from queue with timeout to allow for graceful shutdown
                    try:
                        audio_chunk = await asyncio.wait_for(
                            self._audio_send_queue.get(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        # Continue loop to check is_active status
                        continue
                    
                    if self.live_request_queue and audio_chunk:
                        # Phase 3: Send audio chunk to ADK
                        try:
                            self.live_request_queue.send_realtime(
                                genai_types.Blob(data=audio_chunk, mime_type="audio/pcm")
                            )
                            logger.debug(f"Sent audio chunk to ADK: {len(audio_chunk)} bytes")
                        except Exception as e:
                            logger.error(f"Failed to send audio chunk to ADK: {e}")
                            # Continue processing other chunks even if one fails
                    
                    self._audio_send_queue.task_done()
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in ADK send loop: {e}")
                    
        except asyncio.CancelledError:
            logger.info("ADK send loop cancelled")
        except Exception as e:
            logger.exception(f"Error in ADK send loop: {e}")
            self.is_active = False
        finally:
            logger.info("ADK send loop finished")

    async def _process_agent_events_loop(self):
        """
        Process events from ADK agent.
        Phase 4: Enhanced to handle audio and text content from ADK.
        """
        logger.info("ADK agent events loop started")
        try:
            if not self.live_events:
                logger.error("No live_events available for processing")
                return

            async for event in self.live_events:
                if not self.is_active:
                    break

                if event:
                    # Enhanced logging to debug audio issues
                    logger.debug(f"DEBUG: Received ADK event type: {type(event)}")
                    
                    # Log event attributes for debugging
                    if hasattr(event, '__dict__'):
                        logger.debug(f"DEBUG: Event attributes: {list(event.__dict__.keys())}")
                    
                    # Check if this is a partial or complete event (important for audio)
                    if hasattr(event, 'partial'):
                        logger.debug(f"DEBUG: Event is partial: {event.partial}")
                    
                    # Handle turn completion and interruption events
                    if hasattr(event, 'turn_complete') and event.turn_complete:
                        logger.debug("ADK: Turn complete")
                    
                    if hasattr(event, 'interrupted') and event.interrupted:
                        logger.debug("ADK: Turn interrupted")
                    
                    # Enhanced content processing with detailed logging
                    if hasattr(event, 'content') and event.content:
                        logger.debug(f"DEBUG: Event has content of type: {type(event.content)}")
                        if hasattr(event.content, 'parts') and event.content.parts:
                            logger.debug(f"DEBUG: Content has {len(event.content.parts)} parts")
                            for i, part in enumerate(event.content.parts):
                                logger.debug(f"DEBUG: Part {i} type: {type(part)}")
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    logger.debug(f"DEBUG: Part {i} has inline_data with mime_type: {getattr(part.inline_data, 'mime_type', 'None')}")
                                    if hasattr(part.inline_data, 'data'):
                                        data_len = len(part.inline_data.data) if part.inline_data.data else 0
                                        logger.debug(f"DEBUG: Part {i} inline_data has {data_len} bytes of data")
                                if hasattr(part, 'text') and part.text:
                                    logger.debug(f"DEBUG: Part {i} has text: {part.text[:50]}...")
                            await self._process_event_content_parts(event.content.parts, event)
                        else:
                            logger.debug("DEBUG: Content has no parts or parts is empty")
                    else:
                        logger.debug("DEBUG: Event has no content")
                    
        except asyncio.CancelledError:
            logger.info("ADK agent events loop cancelled")
        except StopAsyncIteration:
            logger.info("ADK live events stream closed")
        except Exception as e:
            logger.exception(f"Error in ADK agent events loop: {e}")
            self.is_active = False
        finally:
            logger.info("ADK agent events loop finished")

    async def _process_event_content_parts(self, parts, event=None):
        """
        Process content parts from ADK events.
        Phase 4: Handle both audio and text content.
        
        Args:
            parts: List of content parts from ADK event
            event: The full event object for additional context
        """
        try:
            event_partial = getattr(event, 'partial', None) if event else None
            logger.debug(f"DEBUG: Processing {len(parts)} parts, event partial: {event_partial}")
            
            for i, part in enumerate(parts):
                logger.debug(f"DEBUG: Processing part {i} of {len(parts)}")
                logger.debug(f"DEBUG: Part {i} has inline_data: {hasattr(part, 'inline_data') and part.inline_data is not None}")
                logger.debug(f"DEBUG: Part {i} has text: {hasattr(part, 'text') and part.text is not None}")
                
                # Process ADK Audio Output
                if hasattr(part, 'inline_data') and part.inline_data:
                    logger.debug(f"DEBUG: Calling _process_audio_part for part {i}")
                    await self._process_audio_part(part)
                
                # Process ADK Text Output (Transcription)
                if hasattr(part, 'text') and part.text:
                    logger.debug(f"DEBUG: Calling _process_text_part for part {i}")
                    await self._process_text_part(part)
                    
        except Exception as e:
            logger.error(f"Error processing event content parts: {e}")

    async def _process_audio_part(self, part):
        """
        Process audio content from ADK.
        Phase 4: Convert 24kHz LPCM16 to 8kHz MuLaw for Twilio.
        
        Args:
            part: Content part containing audio data
        """
        try:
            logger.info(f"Processing audio part - has inline_data: {hasattr(part, 'inline_data')}")
            if hasattr(part, 'inline_data') and part.inline_data:
                logger.debug(f"DEBUG: inline_data mime_type: {getattr(part.inline_data, 'mime_type', 'None')}")
                logger.debug(f"DEBUG: inline_data has data: {hasattr(part.inline_data, 'data') and part.inline_data.data is not None}")
                
            if (hasattr(part, 'inline_data') and part.inline_data and
                part.inline_data.mime_type and
                part.inline_data.mime_type.startswith("audio/pcm") and
                part.inline_data.data):
                
                pcm_24khz_audio = part.inline_data.data
                logger.info(f"SUCCESS: Received ADK audio: {len(pcm_24khz_audio)} bytes at 24kHz")
                
                # Send raw 24kHz PCM audio to callback - let WebSocket handler do the conversion
                if self._audio_output_callback:
                    await self._audio_output_callback(pcm_24khz_audio)
                    logger.info("Raw 24kHz PCM audio sent to output callback")
                else:
                    logger.warning("No audio output callback set")
            else:
                logger.debug("DEBUG: Audio part does not meet criteria for processing")
                    
        except Exception as e:
            logger.error(f"Error processing audio part: {e}")

    async def _process_text_part(self, part):
        """
        Process text content from ADK.
        Phase 4: Handle transcribed text for logging.
        
        Args:
            part: Content part containing text data
        """
        try:
            text_data = part.text.strip()
            if text_data:
                logger.info(f"ADK text output: {text_data}")
                
                # Send to text output callback if available
                if self._text_output_callback:
                    await self._text_output_callback(text_data)
                    logger.info("Text sent to output callback")
                else:
                    logger.info("No text output callback set")
            else:
                logger.debug("DEBUG: Text part has empty text after strip")
                    
        except Exception as e:
            logger.error(f"Error processing text part: {e}")

    # Legacy methods for compatibility (will be removed in later phases)
    async def signal_end_of_user_turn(self):
        """Legacy method - ADK handles turn detection automatically."""
        logger.info("ADK handles turn detection automatically via VAD")