# Refactoring Plan: `app/twilio_integration/websockets.py` for Sample Audio Playback

**Date:** 2025-06-07

**Objective:** Modify the WebSocket handler in [`app/twilio_integration/websockets.py`](app/twilio_integration/websockets.py:1) to remove all Gemini AI integration and instead play a pre-recorded audio file ([`sample_audio/output.wav`](sample_audio/output.wav)) in 100ms chunks to Twilio upon call connection. This will utilize the existing audio queueing mechanism.

## 1. Remove Gemini-Related Code and Imports:

*   **Imports:**
    *   Remove: `from app.gemini_integration.streaming import GeminiStreamingClient` from [`app/twilio_integration/websockets.py`](app/twilio_integration/websockets.py:1).
*   **Class `TwilioMediaStreamHandler` Attributes:**
    *   Remove: `self.gemini_client: Optional[GeminiStreamingClient] = None`
    *   Remove: `self._user_speech_timer: Optional[asyncio.TimerHandle] = None` (and `_silence_threshold_sec` if solely for Gemini VAD).
*   **Method `_handle_stream_start`:**
    *   Remove all code related to `GeminiStreamingClient` initialization, callback setup (`self.gemini_client.set_callbacks(...)`), and `self.gemini_client.start_session(...)` call.
*   **Method `_process_message`:**
    *   In the `mark` event handling (`elif msg.event == "mark":`), remove logic related to `mark_name == "user_finished_speaking"` and `self.gemini_client.signal_end_of_user_turn()`.
*   **Method `_reset_user_speech_timer`:**
    *   Remove this entire method.
*   **Method `_handle_media_message`:**
    *   Remove all Gemini-specific logic, specifically the call to `audio_processor.process_twilio_to_gemini(...)` and `self.gemini_client.send_audio_chunk(...)`. The method can be simplified to log the media event or be mostly emptied.
*   **Method `_handle_stream_stop`:**
    *   Remove `self.gemini_client.stop_session()` call.
    *   Remove `self._user_speech_timer.cancel()` if present.
*   **Method `_handle_gemini_text_response`:**
    *   Remove this entire method.
*   **Method `_cleanup`:**
    *   Remove `self._user_speech_timer.cancel()` if present.
    *   Remove `self.gemini_client.stop_session()` and setting `self.gemini_client = None`.

## 2. Add New Imports:

*   Ensure the following imports are present at the top of [`app/twilio_integration/websockets.py`](app/twilio_integration/websockets.py:1):
    ```python
    import wave
    import audioop # For mono conversion if needed
    # from app.config import settings # Should already be there or ensure it is
    # from app.audio_processing.utils import audio_processor # Should already be there
    ```

## 3. Implement Sample Audio Playback Logic:

*   **Create a new asynchronous method `_play_sample_audio(self)` in `TwilioMediaStreamHandler`:**
    This method will load, chunk, process, and queue the audio file.

    ```python
    async def _play_sample_audio(self):
        try:
            wav_path = "sample_audio/output.wav" # Relative to project root
            logger.info(f"Starting playback of sample audio: {wav_path}")

            with wave.open(wav_path, 'rb') as wf:
                source_wav_rate = wf.getframerate()  # Detected sample rate of the input WAV
                source_wav_width = wf.getsampwidth() # Bytes per sample for the source WAV
                source_wav_channels = wf.getnchannels()
                num_frames = wf.getnframes()

                # Determine the target intermediate rate for the audio before it's passed
                # to the existing processing pipeline (audio_processor.process_gemini_to_twilio).
                # This rate should match the 'input_rate' parameter of 'process_gemini_to_twilio'.
                # It defaults to settings.gemini_output_sample_rate or 24000 Hz.
                target_intermediate_rate = getattr(settings, 'gemini_output_sample_rate', 24000)
                
                # Calculate frames to read for 100ms chunk at the source WAV's original sample rate
                frames_per_100ms_chunk = int(source_wav_rate * 0.100) # 0.100 seconds = 100ms

                total_frames_read = 0
                while total_frames_read < num_frames:
                    if not self.is_active:
                        logger.info("Stopping sample audio playback as handler is no longer active.")
                        break

                    frames_to_read = min(frames_per_100ms_chunk, num_frames - total_frames_read)
                    raw_frames = wf.readframes(frames_to_read)
                    total_frames_read += frames_to_read

                    if not raw_frames: # End of file or error
                        break 

                    current_chunk_processed = raw_frames

                    # 1. Convert to mono if the source WAV is stereo
                    if source_wav_channels == 2:
                        # audioop.tomono expects sample width (bytes per sample)
                        current_chunk_processed = audioop.tomono(current_chunk_processed, source_wav_width, 0.5, 0.5)
                    
                    # 2. Resample to the 'target_intermediate_rate' if different from source WAV rate
                    # The audio_processor.resample_audio method also expects sample_width.
                    if source_wav_rate != target_intermediate_rate:
                        current_chunk_processed = audio_processor.resample_audio(
                            current_chunk_processed,
                            source_wav_rate,
                            target_intermediate_rate,
                            source_wav_width # Sample width of the (potentially mono) data before resampling
                        )
                    
                    # Now current_chunk_processed is mono PCM at target_intermediate_rate.
                    # This is ready to be passed to _send_audio_to_twilio, which will then
                    # use audio_processor.process_gemini_to_twilio to convert it to
                    # Twilio's expected format (e.g., 8kHz mu-law).
                    await self._send_audio_to_twilio(current_chunk_processed)
                    logger.debug(f"Queued {len(current_chunk_processed)} bytes of sample audio for Twilio.")
                    
                    # Yield control to allow other tasks to run, including the audio sender.
                    await asyncio.sleep(0.01) 

            logger.info(f"Finished processing and queueing sample audio: {wav_path}")

        except FileNotFoundError:
            logger.error(f"Sample audio file not found: {wav_path}")
        except wave.Error as e:
            logger.error(f"Error processing WAV file {wav_path}: {e}")
        except Exception as e:
            logger.error(f"Error in _play_sample_audio: {e}", exc_info=True)
    ```

*   **Call `_play_sample_audio` from `_handle_stream_start`:**
    After the `CallSession` is created and stored, start the audio playback as a background task.
    Modify `_handle_stream_start` in [`app/twilio_integration/websockets.py`](app/twilio_integration/websockets.py:1) as follows:
    ```python
    # Inside _handle_stream_start, after self.call_session is set up:
    # ... (existing session setup code from original file) ...
    #
    # logger.info(f"Media stream started: {self.stream_sid} for call: {call_sid}")
    #
    # self.call_session = CallSession(...)
    # if call_sid:
    #     active_sessions[call_sid] = self.call_session
    #
    # # --- REMOVE Gemini client initialization here ---
    #
    # # Start playing the sample audio file
    # if self.is_active: # Ensure connection is still considered active
    #    logger.info(f"Initiating sample audio playback for call: {call_sid}")
    #    asyncio.create_task(self._play_sample_audio())
    # else:
    #    logger.warning("WebSocket connection became inactive before sample audio playback could start.")
    #
    # logger.info(f"Stream start handled for call: {call_sid}") # Ensure this log reflects the new reality
    # ...
    ```

## 4. Audio Processing Pipeline Considerations:

*   The method `_send_audio_to_twilio` calls either `_queue_audio_for_twilio` or `_send_audio_immediate`.
*   Both of these currently use `audio_processor.process_gemini_to_twilio()`.
*   This function (`process_gemini_to_twilio`) expects PCM data at an `input_rate` (which `_play_sample_audio` now prepares as `target_intermediate_rate`, defaulting to `settings.gemini_output_sample_rate` or 24kHz) and converts it to `settings.output_sample_rate` (e.g., 8kHz) mu-law, then base64 encodes.
*   **Decision:** The function `audio_processor.process_gemini_to_twilio` will **not** be renamed for now, but its usage context has changed. The logic within `_play_sample_audio` correctly prepares data for its expected input format and rate.

## 5. Configuration Settings ([`app/config.py`](app/config.py:1)):

*   Ensure `settings.output_sample_rate` is correctly set for Twilio (typically 8000 Hz).
*   The `target_intermediate_rate` used in `_play_sample_audio` will default to `settings.gemini_output_sample_rate` if available, otherwise 24000 Hz. This rate serves as the input for the `process_gemini_to_twilio` function.

## 6. Diagram of New Audio Flow:

```mermaid
graph TD
    A[Twilio Call Connects] --> B{WebSocket Connection};
    B -- Start Event --> C[_handle_stream_start];
    C --> D[Create CallSession];
    C --> E[asyncio.create_task(_play_sample_audio)];

    subgraph _play_sample_audio Task
        F[Open sample_audio/output.wav] --> G[Detect WAV params (rate, width, channels)];
        G --> H{Read 100ms Chunk (PCM_source_wav)};
        H -- WAV frames --> I[Convert to Mono (if stereo)];
        I -- Mono PCM_source_wav --> J[Resample to target_intermediate_rate (e.g., 24kHz)];
        J -- Mono PCM_intermediate_rate --> K[Call self._send_audio_to_twilio(PCM_intermediate_rate)];
        K --> L{_audio_queue};
        H -- More Chunks? --> H;
        H -- No More Chunks --> M[Log "Finished Playback"];
    end

    subgraph _send_audio_to_twilio / _queue_audio_for_twilio
        N[Receive PCM_intermediate_rate] --> O[audio_processor.process_gemini_to_twilio(PCM_intermediate_rate)];
        O -- Processes to --> P[Twilio Format: 8kHz MuLaw Base64];
        P --> Q[Format JSON Media Message + Mark Message];
        Q --> L;
        L -- audio chunk --> R[_audio_sender_loop];
    end
    
    R -- Sends to --> S[Twilio];
```

This plan outlines the necessary changes to achieve the desired audio playback functionality.