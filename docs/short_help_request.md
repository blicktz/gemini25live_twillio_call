# Short Version - For Twitter/Discord/Slack

**Gemini Live API HTTP 404 Help Needed** 🚨

Getting consistent 404 errors when connecting to Gemini Live API via Vertex AI WebSocket. 

✅ Verified: Auth, billing, APIs enabled, service account permissions
❌ Tested: Multiple models (`gemini-2.0-flash-exp`, `gemini-exp-1206`), regions (`us-central1`, `us-east1`), all return 404

```python
# This fails with HTTP 404
client = genai.Client(vertexai=True, project="my-project", location="us-central1")
session = await client.aio.live.connect(model="gemini-2.0-flash-exp", config=config)
```

**Questions:**
- Is Live API generally available or needs special access?
- Correct model names for Live API?
- Missing IAM roles beyond `aiplatform.user`?

Using `google-genai==0.8.0`. Any insights appreciated! 

#GoogleCloud #VertexAI #GeminiAPI #WebSockets