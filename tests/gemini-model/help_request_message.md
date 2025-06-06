# Gemini Live API HTTP 404 Error - Need Help with WebSocket Connection

## Problem Summary
I'm trying to connect to Google's Gemini Live API using Vertex AI but getting consistent HTTP 404 errors when attempting to establish WebSocket connections. I've verified authentication, billing, and API enablement, but all model variations return 404.

## Setup Details
- **Project**: `twilio-gemini25-live-api`
- **Region**: `us-central1` (also tested us-east1, us-west1, europe-west1)
- **Python SDK**: `google-genai` package
- **API Version**: `v1alpha`
- **Authentication**: Service account with `roles/aiplatform.user`

## Environment Configuration
```bash
# .env file
GOOGLE_CLOUD_PROJECT=twilio-gemini25-live-api
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
GEMINI_MODEL=gemini-2.5-flash-preview-native-audio-dialog
```

## Code Implementation
```python
from google import genai
from google.genai.types import LiveConnectConfig, SpeechConfig, VoiceConfig

class GeminiStreamingClient:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.client = genai.Client(
            vertexai=True,
            project="twilio-gemini25-live-api",
            location="us-central1",
            http_options=types.HttpOptions(api_version="v1alpha")
        )
    
    async def start_session(self, initial_prompt: str):
        session_config = LiveConnectConfig(
            response_modalities=["AUDIO", "TEXT"]
        )
        
        self._session_context_manager = self.client.aio.live.connect(
            model=self.model_name,
            config=session_config
        )
        
        # This line fails with HTTP 404
        self.live_session = await self._session_context_manager.__aenter__()
```

## Error Details
```
websockets.exceptions.InvalidStatus: server rejected WebSocket connection: HTTP 404

Traceback:
  File "google/genai/live.py", line 735, in connect
    async with connect(uri, additional_headers=headers) as ws:
  File "websockets/asyncio/client.py", line 487, in __aenter__
    return await self
  File "websockets/asyncio/client.py", line 446, in __await_impl__
    await self.connection.handshake(*self.handshake_args)
```

## What I've Verified ✅
1. **Authentication**: Service account credentials are valid (regenerated fresh key)
2. **Billing**: Enabled and working (`gcloud billing projects describe` succeeds)
3. **APIs Enabled**: 
   - `aiplatform.googleapis.com` ✅
   - `generativelanguage.googleapis.com` ✅
4. **Permissions**: Service account has `roles/aiplatform.user`
5. **Project Access**: Can create Vertex AI clients successfully

## What I've Tested ❌
**Model Names Tested (all return 404):**
- `gemini-2.0-flash-exp`
- `gemini-exp-1206`
- `gemini-2.5-flash-preview-native-audio-dialog`
- `models/gemini-2.0-flash-exp`
- `models/gemini-2.5-flash-preview-native-audio-dialog`

**Regions Tested (all return 404):**
- `us-central1`
- `us-east1`
- `us-west1`
- `europe-west1`

**API Approaches Tested:**
- Vertex AI with service account ❌
- Direct Google AI API (no Live models found) ❌

## Diagnostic Commands Run
```bash
# Verify project and billing
gcloud config list
gcloud billing projects describe twilio-gemini25-live-api

# Check enabled APIs
gcloud services list --enabled --filter="name:aiplatform OR name:generativeai"

# Test service account
gcloud iam service-accounts list --filter="email:gemini-live-api@twilio-gemini25-live-api.iam.gserviceaccount.com"

# Regenerate credentials
gcloud iam service-accounts keys create credentials.json --iam-account=gemini-live-api@twilio-gemini25-live-api.iam.gserviceaccount.com
```

## Questions
1. **Is Gemini Live API generally available through Vertex AI?** Or does it require special access/allowlisting?

2. **Are there specific model names** that work with the Live API? The documentation examples don't seem to match what's available.

3. **Is there a region restriction** for Live API availability?

4. **Do I need additional IAM roles** beyond `roles/aiplatform.user`?

5. **Is there a different endpoint or API version** I should be using?

## Additional Context
- Using this for a Twilio voice integration project
- Need real-time audio streaming capabilities
- Willing to use alternative approaches if Live API isn't available
- Have successfully used standard Gemini API for text generation

## Package Versions
```
google-genai==0.8.0
google-cloud-aiplatform==1.71.1
```

Any help or insights would be greatly appreciated! Has anyone successfully connected to the Gemini Live API through Vertex AI recently?

---
**Tags**: google-cloud-platform, vertex-ai, gemini-api, websockets, python, live-api