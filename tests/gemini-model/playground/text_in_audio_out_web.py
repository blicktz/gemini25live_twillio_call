import asyncio
import numpy as np

import sys
import os
import asyncio
from pathlib import Path
# Add the root directory to Python path so we can import from app
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

# Set the absolute path to credentials file to fix Google Auth issue
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(root_dir / 'credentials.json')
from app.config import settings

# Import our web display instead of IPython.display
from web_display import display, Markdown, Audio, web_display

from google import genai
from google.genai.types import (
    Content,
    LiveConnectConfig,
    HttpOptions,
    Modality,
    Part,
    SpeechConfig,
    VoiceConfig,
    PrebuiltVoiceConfig,
)

client = genai.Client(
    vertexai=True,
    project=settings.google_cloud_project,
    location=settings.google_cloud_location,
)

voice_name = "Aoede"  # @param ["Aoede", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]

config = LiveConnectConfig(
    response_modalities=["AUDIO"],
    speech_config=SpeechConfig(
        voice_config=VoiceConfig(
            prebuilt_voice_config=PrebuiltVoiceConfig(
                voice_name=voice_name,
            )
        ),
    ),
)

MODEL_ID = "gemini-2.0-flash-live-preview-04-09"

async def main():
    # Start the web server
    print("Starting web display server...")
    web_display.start_server()
    print("Web display available at: http://127.0.0.1:5000")
    
    async with client.aio.live.connect(
        model=MODEL_ID,
        config=config,
    ) as session:
        text_input = "Hello? Gemini are you there?"
        display(Markdown(f"**Input:** {text_input}"))

        await session.send_client_content(
            turns=Content(role="user", parts=[Part(text=text_input)]))

        audio_data = []
        async for message in session.receive():
            if (
                message.server_content.model_turn
                and message.server_content.model_turn.parts
            ):
                for part in message.server_content.model_turn.parts:
                    if part.inline_data:
                        audio_data.append(
                            np.frombuffer(part.inline_data.data, dtype=np.int16)
                        )

        if audio_data:
            display(Audio(np.concatenate(audio_data), rate=24000, autoplay=False))
            print("Audio generated and available in web interface!")
        
        # Keep the server running for a bit so you can interact with the web interface
        print("Web interface is running. Press Ctrl+C to stop.")
        try:
            await asyncio.sleep(60)  # Keep running for 60 seconds
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            web_display.cleanup()

if __name__ == "__main__":
    asyncio.run(main())