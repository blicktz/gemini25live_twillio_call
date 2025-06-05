import asyncio
import base64
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.audio_processing.utils import decode_mulaw, encode_mulaw, resample_audio
from app.core.models import TwilioMediaMessage, TwilioStreamStop
from app.gemini_integration.streaming import GeminiStreamingClient
# from app.config import settings # Not directly needed here for now

# Configure basic logging
# Assuming LOG_LEVEL is available via app.config.settings if we were to import it
# For now, let's set a default if settings are not directly imported/used here.
logger = logging.getLogger(__name__)
# BasicConfig should ideally be in main.py or a central logging setup.
# If not configured elsewhere, this will ensure logs are visible.
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

# Store the active Gemini audio processing task globally or within a class context
# For a single WebSocket endpoint function, we can manage it within the function's scope.
# If multiple connections need to be managed by a class, this would be part of the class state.
active_gemini_task = None

async def _handle_gemini_audio_responses(
    websocket: WebSocket,
    stream_sid: str,
    gemini_client: GeminiStreamingClient,
    input_audio_chunk: bytes
):
    """
    Task to send a single audio chunk to Gemini and stream responses back to Twilio.
    This task can be cancelled if new user audio (barge-in) is received.
    """
    logger.info(f"[{stream_sid}] Starting task to send audio to Gemini and relay responses.")
    try:
        async for gemini_audio_chunk_24k in gemini_client.send_audio(input_audio_chunk):
            if not gemini_audio_chunk_24k:
                continue

            # logger.debug(f"[{stream_sid}] Received Gemini audio chunk (24kHz), size: {len(gemini_audio_chunk_24k)}")

            # Audio Processing (Gemini -> Twilio)
            audio_lpcm16_8k_gemini = resample_audio(gemini_audio_chunk_24k, input_rate=24000, output_rate=8000, width=2)
            # logger.debug(f"[{stream_sid}] Resampled to 8kHz LPCM, size: {len(audio_lpcm16_8k_gemini)}")

            audio_mulaw_8k_gemini = encode_mulaw(audio_lpcm16_8k_gemini, width=2)
            # logger.debug(f"[{stream_sid}] Encoded to MuLaw, size: {len(audio_mulaw_8k_gemini)}")

            payload_to_twilio_b64 = base64.b64encode(audio_mulaw_8k_gemini).decode('utf-8')

            # Send to Twilio
            twilio_response = TwilioMediaMessage(stream_sid=stream_sid, event="media")
            twilio_response.set_payload(payload_to_twilio_b64)

            # logger.debug(f"[{stream_sid}] Sending media message to Twilio WebSocket.")
            await websocket.send_text(twilio_response.to_json())

    except asyncio.CancelledError:
        logger.info(f"[{stream_sid}] Gemini audio response task was cancelled (likely due to barge-in).")
    except WebSocketDisconnect:
        logger.warning(f"[{stream_sid}] WebSocket disconnected while handling Gemini responses.")
        # Attempt to stop Gemini session if WebSocket disconnects during this task
        if gemini_client.is_active:
            await gemini_client.stop_session()
    except Exception as e:
        logger.exception(f"[{stream_sid}] Error in Gemini audio response task: {e}")
        # Consider sending a clear or error message if appropriate, or just closing.
    finally:
        logger.info(f"[{stream_sid}] Gemini audio response task finished.")


async def twilio_media_stream_ws_endpoint(websocket: WebSocket):
    """
    Handles the Twilio media stream WebSocket connection.
    Receives audio from Twilio, sends it to Gemini, receives audio from Gemini, and sends it back to Twilio.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted from Twilio.")

    gemini_client = GeminiStreamingClient()
    # TODO: Make initial prompt configurable, perhaps from request query params or settings
    initial_prompt = "You are a friendly and helpful AI voice assistant on a phone call. Respond naturally as if you are speaking. Keep your responses concise and to the point."
    stream_sid = None

    # This variable will hold the task that processes and sends Gemini's audio output.
    # It allows us to cancel it if the user barges in.
    current_gemini_output_task: asyncio.Task = None

    try:
        while True:
            message_str = await websocket.receive_text()
            message = json.loads(message_str)
            event = message.get("event")

            if not stream_sid and message.get("streamSid"):
                 stream_sid = message["streamSid"] # Capture streamSid from any message that has it

            if event == "connected":
                logger.info(f"[{stream_sid if stream_sid else 'UNKNOWN_SID'}] Twilio 'connected' event: {message}")
                # stream_sid is often not available in the 'connected' event itself,
                # but rather in the 'start' event.

            elif event == "start":
                if 'start' in message and 'streamSid' in message['start']:
                    stream_sid = message['start']['streamSid']
                logger.info(f"[{stream_sid}] Twilio 'start' event: {message['start']}")

                # Start the Gemini session
                try:
                    await gemini_client.start_session(initial_prompt=initial_prompt)
                    logger.info(f"[{stream_sid}] Gemini session started successfully.")
                    # Optional: Send an initial silent frame or a pre-recorded greeting from AI
                    # For MVP, we wait for user to speak first.
                except Exception as e:
                    logger.error(f"[{stream_sid}] Failed to start Gemini session: {e}")
                    # TODO: Send a clear message if possible, or just close.
                    # For now, break the loop, which will lead to closing the WebSocket.
                    break


            elif event == "media":
                # logger.debug(f"[{stream_sid}] Twilio 'media' event, payload: {message['media']['payload'][:20]}...")
                payload_b64 = message['media']['payload']

                # Audio Processing (Twilio -> Gemini)
                audio_mulaw_8k = base64.b64decode(payload_b64)
                audio_lpcm16_8k = decode_mulaw(audio_mulaw_8k, width=2) # Twilio sends MuLaw, decode to LPCM
                audio_lpcm16_16k = resample_audio(audio_lpcm16_8k, input_rate=8000, output_rate=16000, width=2)

                # If Gemini is currently "speaking" (i.e., sending audio back),
                # receiving new audio from the user (barge-in) should interrupt Gemini.
                if current_gemini_output_task and not current_gemini_output_task.done():
                    logger.info(f"[{stream_sid}] Barge-in detected. Cancelling current Gemini audio output task.")
                    current_gemini_output_task.cancel()
                    try:
                        await current_gemini_output_task # Allow task to process cancellation
                    except asyncio.CancelledError:
                        logger.info(f"[{stream_sid}] Current Gemini output task successfully cancelled.")
                    current_gemini_output_task = None # Clear the cancelled task

                # Send audio to Gemini and handle its response in a new background task.
                # This allows the main loop to immediately return to `websocket.receive_text()`
                # to listen for more messages from Twilio (e.g., more media, or a stop event).
                current_gemini_output_task = asyncio.create_task(
                    _handle_gemini_audio_responses(websocket, stream_sid, gemini_client, audio_lpcm16_16k)
                )

            elif event == "stop":
                logger.info(f"[{stream_sid}] Twilio 'stop' event: {message['stop']}")
                if current_gemini_output_task and not current_gemini_output_task.done():
                    logger.info(f"[{stream_sid}] Stop event received. Cancelling ongoing Gemini audio output task.")
                    current_gemini_output_task.cancel()
                    try:
                        await current_gemini_output_task
                    except asyncio.CancelledError:
                         logger.info(f"[{stream_sid}] Ongoing Gemini output task cancelled due to stop event.")
                await gemini_client.stop_session()
                logger.info(f"[{stream_sid}] Call stopped. Gemini session ended.")
                break # Exit the loop, will lead to finally block

            else:
                logger.warning(f"[{stream_sid if stream_sid else 'UNKNOWN_SID'}] Received unknown event type: {event}, message: {message}")

    except WebSocketDisconnect:
        logger.info(f"[{stream_sid if stream_sid else 'N/A'}] WebSocket disconnected by Twilio (or client).")
    except Exception as e:
        logger.exception(f"[{stream_sid if stream_sid else 'N/A'}] Error in WebSocket handler: {e}")
    finally:
        logger.info(f"[{stream_sid if stream_sid else 'N/A'}] Cleaning up WebSocket connection.")
        if current_gemini_output_task and not current_gemini_output_task.done():
            logger.info(f"[{stream_sid if stream_sid else 'N/A'}] Ensuring cancellation of active Gemini output task during cleanup.")
            current_gemini_output_task.cancel()
            try:
                await current_gemini_output_task # Wait for task to acknowledge cancellation
            except asyncio.CancelledError:
                logger.info(f"[{stream_sid if stream_sid else 'N/A'}] Active Gemini output task cancelled during final cleanup.")
            except Exception as e_task:
                logger.error(f"[{stream_sid if stream_sid else 'N/A'}] Error during final cancellation of Gemini task: {e_task}")

        if gemini_client and gemini_client.is_active:
            logger.info(f"[{stream_sid if stream_sid else 'N/A'}] Ensuring Gemini session is stopped.")
            await gemini_client.stop_session()

        # FastAPI's WebSocket has a .close() method, but it's typically called by the server
        # when the handler finishes or if an unhandled exception occurs.
        # Explicitly closing here might be redundant or even problematic if FastAPI handles it.
        # For now, we rely on FastAPI's default behavior upon exiting the handler.
        logger.info(f"[{stream_sid if stream_sid else 'N/A'}] WebSocket connection closed.")

# Note: This endpoint needs to be added to a FastAPI router, e.g.:
# from fastapi import APIRouter
# router = APIRouter()
# router.add_websocket_route("/ws/media-stream", twilio_media_stream_ws_endpoint)
# app.include_router(router)
