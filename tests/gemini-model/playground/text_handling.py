# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
# https://cloud.google.com/vertex-ai/generative-ai/docs/live-api

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


from google import genai
from google.genai.types import (
    Content,
    LiveConnectConfig,
    Modality,
    Part,
)

client = genai.Client(
    vertexai=True,
    project=settings.google_cloud_project,
    location=settings.google_cloud_location
)
MODEL_ID = "gemini-2.0-flash-live-preview-04-09"

async def main():
    async with client.aio.live.connect(
        model=MODEL_ID,
        config=LiveConnectConfig(response_modalities=[Modality.TEXT]),
    ) as session:
        text_input = "Hello? Gemini, are you there?"
        print("> ", text_input, "\n")
        await session.send_client_content(
            turns=Content(role="user", parts=[Part(text=text_input)])
        )

        response = []

        async for message in session.receive():
            if message.text:
                response.append(message.text)

        print("".join(response))

if __name__ == "__main__":
    asyncio.run(main())

# Example output:
# >  Hello? Gemini, are you there?
# Yes, I'm here. What would you like to talk about?
  