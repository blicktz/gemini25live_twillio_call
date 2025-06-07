# Final Definitive Refactoring Plan: app/gemini_integration/streaming.py with Google ADK

This plan outlines the steps to refactor the `GeminiStreamingClient` class to utilize Google ADK components, replacing the previous Gemini Live API client logic. The focus is on creating a robust, audio-only agent for Twilio voice call integration, using the specified Gemini model.

```mermaid
graph TD
    A[Start: Refactor app/gemini_integration/streaming.py] --> B(1. Update Dependencies & Configuration);
    B --> B1(1.1. Add 'google-adk' and ensure 'google-genai' is present in requirements.txt);
    B --> B2(1.2. Confirm Vertex AI authentication via environment variables is used by ADK);
    B --> B3(1.3. Ensure `settings.gemini_model` is configured to "gemini-2.0-flash-live-preview-04-09");

    A --> C(2. Modify GeminiStreamingClient Class);
    C --> C1(2.1. Initialization (`__init__`));
    C1 --> C1a(Instantiate `self.session_service = InMemorySessionService()`);
    C1 --> C1b(Import `root_agent` from `app.gemini_integration.adk_agent`);
    C1 --> C1c(Store `self.APP_NAME = "TwilioGeminiADK"`);
    C1 --> C1d(Initialize `self._audio_send_queue = asyncio.Queue()`);
    C1 --> C1e(Initialize ADK-specific attributes: `self.live_request_queue`, `self.live_events`, `self.adk_session`, `self.runner` to None);

    C --> C2(2.2. Session Management (`start_session`, `stop_session`));
    C2 --> C2a(2.2.1. `async def start_session(self, session_id: str)`:);
    C2a --> C2a1(Create ADK Session: `self.adk_session = self.session_service.create_session(...)`);
    C2a --> C2a2(Create Runner: `self.runner = Runner(agent=self.root_agent, ...)` );
    C2a --> C2a3(Define `RunConfig`: `response_modalities=["AUDIO"]`, `speech_config` with voice from `settings.gemini_voice_name`, `output_audio_transcription={}` );
    C2a --> C2a4(Create LiveRequestQueue: `self.live_request_queue = LiveRequestQueue()`);
    C2a --> C2a5(Start Live Run: `self.live_events = self.runner.run_live(...)`);
    C2a --> C2a6(Set `self.is_active = True`);
    C2a --> C2a7(Create and start `_process_agent_events_loop` and `_send_adk_loop` asyncio tasks);

    C2 --> C2b(2.2.2. `async def stop_session(self)`:);
    C2b --> C2b1(Set `self.is_active = False`);
    C2b --> C2b2(Call `self.live_request_queue.close()` if initialized);
    C2b --> C2b3(Cancel `_process_agent_events_loop` and `_send_adk_loop` tasks and await their completion);
    C2b --> C2b4(Call `self.session_service.delete_session(self.adk_session.session_id)` if available and appropriate for `InMemorySessionService`, otherwise clear local references);
    C2b --> C2b5(Clear `self._audio_send_queue`);
    C2b --> C2b6(Reset ADK attributes to None);

    C --> D(3. Adapt Audio Data Flow);
    D --> D1(3.1. `async def send_audio_chunk(self, audio_chunk: bytes)`:);
    D1 --> D1a(Put `audio_chunk` (16kHz LPCM16) onto `self._audio_send_queue`);

    D --> D2(3.2. `async def _send_adk_loop(self)` -- New/Adapted Loop:);
    D2 --> D2a(Continuously get `audio_chunk` from `self._audio_send_queue`);
    D2 --> D2b(Send to ADK: `await self.live_request_queue.send_realtime(types.Blob(data=audio_chunk, mime_type="audio/pcm"))`);

    D --> D3(3.3. `async def _process_agent_events_loop(self)` -- New Loop:);
    D3 --> D3a(Iterate `async for event in self.live_events:`);
    D3 --> D3b(Process ADK Audio Output: `event.content.parts[0].inline_data.data` (24kHz LPCM16));
    D3b --> D3b1(Resample to 8kHz LPCM16 using `app.audio_processing.utils`);
    D3b --> D3b2(Encode to 8kHz MuLaw using `app.audio_processing.utils`);
    D3b --> D3b3(Pass to `self._audio_output_callback(muLaw_audio_data)`);
    D3 --> D3c(Process ADK Text Output (Transcription): `event.content.parts[0].text`);
    D3c --> D3c1(Pass to `self._text_output_callback(text_data)` for logging);
    D3 --> D3d(Handle `event.turn_complete`, `event.interrupted` by logging);

    C --> E(4. Maintain Callbacks (`set_callbacks`));
    E --> E1(4.1. `_audio_output_callback` receives 8kHz MuLaw for Twilio);
    E --> E2(4.2. `_text_output_callback` receives transcribed text for logging);

    A --> F(5. Define `root_agent` in `app/gemini_integration/adk_agent.py`);
    F --> F1(5.1. Agent `process` function receives transcribed text via `AgentContext`);
    F --> F2(5.2. Agent `process` function uses `genai.GenerativeModel(settings.gemini_model)` which must be "gemini-2.0-flash-live-preview-04-09", configured with Vertex AI auth);
    F --> F3(5.3. Agent `process` function returns text for ADK to synthesize to speech);
    F --> F4(5.4. Agent configured with `SystemInstruction` from `settings.system_prompt`);

    A --> G(6. Audio Processing in `app/audio_processing/utils.py`);
    G --> G1(6.1. Twilio Inbound: 8kHz MuLaw -> Decode LPCM -> Resample to 16kHz LPCM16 for ADK);
    G --> G2(6.2. ADK Outbound: 24kHz LPCM16 -> Resample to 8kHz LPCM16 -> Encode to 8kHz MuLaw for Twilio);

    A --> H(7. Implement Robust Error Handling for all ADK operations and async tasks);

    A --> I(8. Phased Implementation & Testing);
    I --> I1(Phase 1: Foundational ADK Setup in GeminiStreamingClient);
    I --> I2(Phase 2: Implement `root_agent` Structure);
    I --> I3(Phase 3: Implement Audio Sending to ADK);
    I --> I4(Phase 4: Implement Audio & Text Receiving from ADK);
    I --> I5(Phase 5: Integrate `root_agent` Logic with Gemini Model);
    I --> I6(Phase 6: End-to-End Testing with Twilio Integration);
```

## Final Definitive Plan Details:

### 1. Update Dependencies & Configuration:
*   Ensure `requirements.txt` includes `google-adk` and `google-genai`.
*   The application will rely on Vertex AI service account authentication (via `GOOGLE_APPLICATION_CREDENTIALS` set in `app/config.py`). This environment-based authentication will be automatically utilized by ADK components and any `google.genai.GenerativeModel` instances.
*   **Crucially, ensure that `settings.gemini_model` (loaded from the environment, e.g., via `GEMINI_MODEL` in your `.env` file and accessed through `app/config.py`) is set to the exact string: `"gemini-2.0-flash-live-preview-04-09"`.**

### 2. Refactor `GeminiStreamingClient` in `app/gemini_integration/streaming.py`:
*   **Initialization (`__init__`)**:
    *   Instantiate `self.session_service = InMemorySessionService()`.
    *   Import `root_agent` from a new file: `from app.gemini_integration.adk_agent import root_agent`. Store it as `self.root_agent`.
    *   Store `self.APP_NAME = "TwilioGeminiADK"`.
    *   Initialize `self._audio_send_queue = asyncio.Queue()`.
    *   Initialize ADK-specific attributes to `None`: `self.live_request_queue`, `self.live_events`, `self.adk_session`, `self.runner`.
*   **Session Management:**
    *   `async def start_session(self, session_id: str)`:
        *   Create ADK Session: `self.adk_session = self.session_service.create_session(app_name=self.APP_NAME, user_id=session_id, session_id=session_id)`.
        *   Create Runner: `self.runner = Runner(app_name=self.APP_NAME, agent=self.root_agent, session_service=self.session_service)`.
        *   Define `RunConfig`:
            ```python
            # Ensure necessary imports:
            # from google.genai import types as genai_types
            # from google.adk.agents.run_config import RunConfig
            # from app.config import settings

            speech_config = genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=settings.gemini_voice_name or "Puck" # From app.config
                    )
                )
            )
            run_config_dict = {
                "response_modalities": ["AUDIO"],
                "speech_config": speech_config,
                "output_audio_transcription": {} # To get text logs of user speech
            }
            run_config = RunConfig(**run_config_dict)
            ```
        *   Create LiveRequestQueue: `self.live_request_queue = LiveRequestQueue()`. (Import `from google.adk.agents import LiveRequestQueue`)
        *   Start Live Run: `self.live_events = self.runner.run_live(session=self.adk_session, live_request_queue=self.live_request_queue, run_config=run_config)`.
        *   Set `self.is_active = True`.
        *   Create and start asyncio tasks: `self._event_loop_task = asyncio.create_task(self._process_agent_events_loop())` and `self._send_loop_task = asyncio.create_task(self._send_adk_loop())`.
    *   `async def stop_session(self)`:
        *   Set `self.is_active = False`.
        *   If `self.live_request_queue` is not `None`, call `await self.live_request_queue.close()`.
        *   Cancel `self._event_loop_task` and `self._send_loop_task` if they exist and are not done. Await their completion with `try-except asyncio.CancelledError`.
        *   If `self.adk_session` and `self.session_service` are not `None`, call `self.session_service.delete_session(self.adk_session.session_id)` (Note: `InMemorySessionService` might not have `delete_session`; if not, clearing local references is sufficient for this in-memory implementation).
        *   Clear `self._audio_send_queue`: Loop `get_nowait()` until empty, calling `task_done()`.
        *   Reset ADK-related attributes (`self.live_request_queue`, `self.live_events`, `self.adk_session`, `self.runner`) to `None`.
*   **Audio Data Flow:**
    *   `async def send_audio_chunk(self, audio_chunk: bytes)`: (Called by Twilio integration with 16kHz LPCM16 audio)
        *   If `self.is_active`, `await self._audio_send_queue.put(audio_chunk)`.
    *   `async def _send_adk_loop(self)`:
        *   Loop while `self.is_active`.
        *   `audio_chunk = await self._audio_send_queue.get()`.
        *   `await self.live_request_queue.send_realtime(google.genai.types.Blob(data=audio_chunk, mime_type="audio/pcm"))`.
        *   `self._audio_send_queue.task_done()`.
    *   `async def _process_agent_events_loop(self)`:
        *   Loop `async for event in self.live_events:` (handle `StopAsyncIteration` if `live_events` is closed).
        *   If `event.content` and `event.content.parts`:
            *   For `part` in `event.content.parts`:
                *   **ADK Audio Output:** If `part.inline_data` and `part.inline_data.mime_type.startswith("audio/pcm")`:
                    *   `pcm_24khz_audio = part.inline_data.data`.
                    *   `pcm_8khz_audio = await app.audio_processing.utils.resample_audio(pcm_24khz_audio, from_rate=24000, to_rate=8000, channels=1)`.
                    *   `mulaw_audio = await app.audio_processing.utils.encode_mu_law(pcm_8khz_audio)`.
                    *   If `self._audio_output_callback`, `await self._audio_output_callback(mulaw_audio)`.
                *   **ADK Text Output (Transcription):** If `part.text`:
                    *   If `self._text_output_callback`, `await self._text_output_callback(part.text)`.
        *   If `event.turn_complete` or `event.interrupted`: Log these events.
*   **Callbacks (`set_callbacks`)**: This method remains as is.

### 3. Define `root_agent` in `app/gemini_integration/adk_agent.py`:
*   The agent's `process` function (e.g., `async def my_voice_agent_fn(context: AgentContext)`) will:
    *   Receive user's transcribed speech from `context.history` (e.g., `context.history[-1].parts[0].text` if `context.history[-1].role == "user"`).
    *   Instantiate `model = google.genai.GenerativeModel(settings.gemini_model)`. **`settings.gemini_model` must be configured to `"gemini-2.0-flash-live-preview-04-09"`.** Vertex AI authentication will be handled by the environment.
    *   Generate a text response: `response = await model.generate_content_async(user_text_or_full_history)`.
    *   Return `Output(content=google.genai.types.Content(parts=[google.genai.types.Part.from_text(response.text)]))`.
*   The `root_agent` will be defined with this `process` function and `SystemInstruction(settings.system_prompt)`.
    ```python
    # app/gemini_integration/adk_agent.py
    # Ensure necessary imports:
    # from google.adk.agents import Agent, AgentContext, Output, SystemInstruction
    # from google.genai import types as genai_types
    # import google.generativeai as genai # For GenerativeModel
    # from app.config import settings

    # async def my_voice_agent_fn(context: AgentContext) -> Output | None:
    #     user_input_text = ""
    #     if context.history and context.history[-1].role == "user":
    #         user_input_text = context.history[-1].parts[0].text
    #         # logger.info(f"ADK Agent received user text: {user_input_text}")

    #     if not user_input_text: # Or handle empty input as needed
    #         return None

    #     model = genai.GenerativeModel(settings.gemini_model) # "gemini-2.0-flash-live-preview-04-09"
    #     # Construct prompt for the model, potentially using more history
    #     # For simplicity, using only the last user utterance here
    #     response = await model.generate_content_async(user_input_text)
        
    #     # logger.info(f"ADK Agent sending AI text: {response.text}")
    #     return Output(content=genai_types.Content(parts=[genai_types.Part.from_text(response.text)]))

    # root_agent = Agent(
    #     name="twilio_voice_assistant",
    #     description="AI assistant for Twilio voice calls using Google ADK.",
    #     system_instruction=SystemInstruction(settings.system_prompt),
    #     process=my_voice_agent_fn,
    # )
    ```

### 4. Audio Processing in `app/audio_processing/utils.py`:
*   **Twilio Inbound:** Functions to convert 8kHz MuLaw from Twilio to 16kHz LPCM16 for ADK input.
*   **ADK Outbound:** Functions to convert 24kHz LPCM16 from ADK TTS output to 8kHz MuLaw for Twilio.
*   Ensure these functions are robust and handle potential errors.

### 5. Error Handling:
*   Implement comprehensive `try-except` blocks in all async loops and ADK interaction points.
*   Log errors using the existing `logger`.
*   Ensure `stop_session` is called in `finally` blocks of main processing loops or on critical unrecoverable errors.

### 6. Phased Implementation and Testing:
*   **Phase 1: Foundational ADK Setup in `GeminiStreamingClient`**
    *   Implement `__init__`, `start_session`, and `stop_session` focusing on ADK object creation (`InMemorySessionService`, `Runner`, `LiveRequestQueue`, `RunConfig`, `adk_session`, `live_events`) and basic lifecycle management (task creation/cancellation, `live_request_queue.close()`).
    *   At this stage, the `root_agent` can be a minimal placeholder.
    *   Goal: Verify ADK session can be initiated and terminated cleanly without errors.
*   **Phase 2: Implement `root_agent` Structure**
    *   Create `app/gemini_integration/adk_agent.py`.
    *   Define the `root_agent` with a basic `process` function that logs received context and returns a static text response.
    *   Integrate this `root_agent` into `GeminiStreamingClient`.
    *   Goal: Ensure the `root_agent` is correctly instantiated and linked.
*   **Phase 3: Implement Audio Sending to ADK**
    *   Implement `send_audio_chunk` and the `_send_adk_loop` in `GeminiStreamingClient`.
    *   Ensure audio from Twilio (after processing by `app/audio_processing/utils.py` to 16kHz LPCM16) is correctly queued and sent via `live_request_queue.send_realtime()`.
    *   Goal: Verify audio chunks are sent to ADK without errors. Monitor ADK logs/behavior if possible.
*   **Phase 4: Implement Audio & Text Receiving from ADK**
    *   Implement the `_process_agent_events_loop` in `GeminiStreamingClient`.
    *   Handle incoming ADK events for audio (`part.inline_data`) and text (`part.text`).
    *   For audio, integrate with `app/audio_processing/utils.py` for resampling (24kHz to 8kHz LPCM16) and encoding (to 8kHz MuLaw).
    *   Pass processed audio and text to the respective callbacks.
    *   Goal: Verify that responses (even static ones from the placeholder `root_agent`) are received, processed, and callbacks are invoked.
*   **Phase 5: Integrate `root_agent` Logic with Gemini Model**
    *   Flesh out the `root_agent`'s `process` function to:
        *   Correctly extract user input from `AgentContext`.
        *   Instantiate `google.genai.GenerativeModel("gemini-2.0-flash-live-preview-04-09")`.
        *   Call `model.generate_content_async()` to get AI responses.
        *   Return the AI's text response for TTS.
    *   Goal: Achieve a basic conversational flow where the AI responds to user input.
*   **Phase 6: End-to-End Testing with Twilio Integration**
    *   Connect the fully refactored `GeminiStreamingClient` with the Twilio integration components (`app/twilio_integration/websockets.py`).
    *   Perform comprehensive testing:
        *   Audio quality (inbound and outbound).
        *   Latency.
        *   Barge-in functionality (ADK should handle this based on `output_audio_transcription` and its VAD).
        *   Handling of call start/end.
        *   Robustness under various network conditions and error scenarios.
    *   Goal: A fully functional voice call answering service using ADK.

This phased approach allows for incremental development and testing, making it easier to isolate and address issues at each stage.