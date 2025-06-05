"""WebSocket handler for Twilio media stream processing."""

import json
import logging
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
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
        
    async def handle_connection(self):
        """Handle the WebSocket connection lifecycle."""
        try:
            await self.websocket.accept()
            logger.info("WebSocket connection accepted")
            
            self.is_active = True
            
            # Start listening for messages
            await self._listen_for_messages()
            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
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
                logger.error(f"Error processing WebSocket message: {e}")
                break
    
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
            else:
                logger.debug(f"Received unknown event: {msg.event}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
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
            
            # Initialize Gemini streaming client
            self.gemini_client = GeminiStreamingClient(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                system_prompt=settings.system_prompt
            )
            
            # Start Gemini session and set up audio callback
            await self.gemini_client.start_session()
            self.gemini_client.set_audio_callback(self._send_audio_to_twilio)
            
            logger.info(f"Gemini session started for call: {call_sid}")
            
        except Exception as e:
            logger.error(f"Error handling stream start: {e}")
    
    async def _handle_media_message(self, msg: TwilioMediaMessage):
        """Handle incoming audio media from Twilio.
        
        Args:
            msg: Twilio media message containing audio data
        """
        try:
            if not msg.media or not self.gemini_client:
                return
            
            # Extract audio payload (base64 encoded MuLaw)
            audio_payload = msg.media.get('payload')
            if not audio_payload:
                return
            
            # Convert Twilio audio (8kHz MuLaw) to Gemini format (16kHz PCM)
            pcm_audio = audio_processor.process_twilio_to_gemini(
                audio_payload,
                input_rate=settings.input_sample_rate,
                output_rate=settings.gemini_input_sample_rate
            )
            
            # Send audio to Gemini
            await self.gemini_client.send_audio(pcm_audio)
            
        except Exception as e:
            logger.error(f"Error handling media message: {e}")
    
    async def _handle_stream_stop(self, msg: TwilioMediaMessage):
        """Handle stream stop event from Twilio.
        
        Args:
            msg: Twilio media message containing stop information
        """
        try:
            logger.info(f"Media stream stopped: {self.stream_sid}")
            self.is_active = False
            
            # Stop Gemini session
            if self.gemini_client:
                await self.gemini_client.stop_session()
            
        except Exception as e:
            logger.error(f"Error handling stream stop: {e}")
    
    async def _send_audio_to_twilio(self, audio_data: bytes):
        """Send audio data back to Twilio.
        
        This is called by the Gemini client when it has audio to send.
        
        Args:
            audio_data: PCM audio data from Gemini (typically 24kHz)
        """
        try:
            if not self.is_active or not self.stream_sid:
                return
            
            # Convert Gemini audio (24kHz PCM) to Twilio format (8kHz MuLaw)
            base64_mulaw = audio_processor.process_gemini_to_twilio(
                audio_data,
                input_rate=settings.gemini_output_sample_rate,
                output_rate=settings.output_sample_rate
            )
            
            # Create outbound media message
            outbound_msg = TwilioOutboundMedia(
                streamSid=self.stream_sid,
                media={
                    "payload": base64_mulaw
                }
            )
            
            # Send to Twilio via WebSocket
            await self.websocket.send_text(outbound_msg.json())
            
        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {e}")
    
    async def _cleanup(self):
        """Clean up resources when connection ends."""
        try:
            self.is_active = False
            
            # Stop Gemini session
            if self.gemini_client:
                await self.gemini_client.stop_session()
            
            # Remove from active sessions
            if self.call_session and self.call_session.call_sid in active_sessions:
                del active_sessions[self.call_session.call_sid]
            
            logger.info(f"Cleaned up WebSocket connection for stream: {self.stream_sid}")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def handle_media_stream(websocket: WebSocket):
    """FastAPI WebSocket endpoint handler for Twilio media streams.
    
    Args:
        websocket: FastAPI WebSocket connection
    """
    handler = TwilioMediaStreamHandler(websocket)
    await handler.handle_connection()