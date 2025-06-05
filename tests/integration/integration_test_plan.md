# Integration Test Plan (Local Testing)

This document outlines steps for locally testing the AI Call Answering Service, primarily focusing on the HTTP webhook endpoint using `curl`.

## Prerequisites

1.  **Application Running:** Ensure the FastAPI application is running locally (e.g., `python app/main.py`).
2.  **Environment Variables Set:** Your `.env` file should be configured with necessary values, especially `TWILIO_AUTH_TOKEN` if request validation is enabled.
3.  **`jq` (optional but recommended):** A command-line JSON processor, useful for pretty-printing XML/TwiML responses if converted to JSON or for easier inspection.
4.  **`ngrok` (or similar):** While these tests are local, `ngrok` is mentioned because `BASE_URL` (which might be an ngrok URL) is used by the app. For purely local `curl` tests against `localhost`, ensure `BASE_URL` in your `.env` is something like `http://localhost:8000` if the app uses it to construct WebSocket URLs that appear in the TwiML.

## Testing the Twilio Voice Webhook (`/api/twilio-voice`)

This endpoint is triggered by Twilio when an incoming call is received. It should return TwiML.

### 1. Basic Request (without Signature Validation)

If Twilio request validation is temporarily disabled or not strictly enforced in a local dev environment for this test:

*   **Command:**
    ```bash
    curl -X POST http://localhost:8000/api/twilio-voice \
         -d "CallSid=CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
         -d "From=+1234567890" \
         -d "To=+0987654321" \
         -H "Content-Type: application/x-www-form-urlencoded"
    ```

*   **Expected Result:**
    A TwiML XML response. The `Stream` URL will depend on your `BASE_URL` setting. If `BASE_URL` is `http://localhost:8000`, it might look like this:

    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Connecting to our AI assistant. One moment please.</Say>
        <Start>
            <Stream url="wss://localhost:8000/ws/media-stream"/>
        </Start>
        <Pause length="1"/>
        <Say>If you are hearing this, there was an issue connecting to our AI services. Please hang up and try again.</Say>
        <Hangup/>
    </Response>
    ```
    *Note: The `wss://localhost:8000` part might vary based on how `_get_websocket_url` in `app/twilio_integration/webhooks.py` processes the `BASE_URL` from your `.env` file. If `BASE_URL` is `http://example.com`, it will be `wss://example.com/ws/media-stream`.*

### 2. Request with Twilio Signature Validation

To test with signature validation, you need to generate a valid `X-Twilio-Signature`. This is complex to do manually for a `curl` request because it involves HMAC-SHA1 hashing of the URL and all POST parameters, using your `TWILIO_AUTH_TOKEN`.

**Generating the Signature (Conceptual - requires a helper script):**

You would typically need a small Python script or similar tool that uses the `twilio` library to generate this signature for your specific `curl` request parameters.

```python
# Helper script snippet (e.g., generate_signature.py)
# import os
# from twilio.request_validator import RequestValidator
# from dotenv import load_dotenv

# load_dotenv() # To load .env if your auth token is there

# TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# validator = RequestValidator(TWILIO_AUTH_TOKEN)

# url = "http://localhost:8000/api/twilio-voice" # Or your ngrok URL if testing against it
# params = {
#     "CallSid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
#     "From": "+1234567890",
#     "To": "+0987654321"
# }

# signature = validator.compute_signature(url, params)
# print(signature)
```

*   **Command (assuming you've generated a signature):**
    ```bash
    # Replace YOUR_GENERATED_SIGNATURE with the actual signature
    curl -X POST http://localhost:8000/api/twilio-voice \
         -d "CallSid=CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
         -d "From=+1234567890" \
         -d "To=+0987654321" \
         -H "Content-Type: application/x-www-form-urlencoded" \
         -H "X-Twilio-Signature: YOUR_GENERATED_SIGNATURE"
    ```

*   **Expected Result:**
    Same TwiML as above if the signature is valid. If invalid, you should receive a `403 Forbidden` response with content like `"Invalid signature"`.

## Testing the WebSocket Media Stream (`/ws/media-stream`)

**Directly testing the WebSocket endpoint (`/ws/media-stream`) with `curl` is not feasible for simulating Twilio's bi-directional audio streaming.**

*   **Why `curl` is not suitable:**
    *   `curl` has limited WebSocket support, primarily for simple request-response, not for continuous bi-directional streaming of binary data and JSON messages as Twilio does.
    *   It cannot easily simulate the specific sequence of JSON messages (`connected`, `start`, `media`, `stop`) and base64-encoded audio payloads that Twilio's media stream uses.

*   **Recommended approaches for testing WebSockets:**
    1.  **Actual Twilio Call:** The most reliable way is to configure a Twilio number (as described in the main `README.md`) and make a real call. Monitor the application logs to observe the WebSocket communication and audio processing.
    2.  **Dedicated WebSocket Client Tool:** Use a tool like:
        *   `wscat` (Node.js based command-line tool)
        *   Postman (supports WebSocket requests)
        *   Python `websockets` library client script: Write a small Python script to act as a WebSocket client, sending the expected JSON messages and audio payloads. This offers the most control for simulating Twilio's behavior.

    3.  **Unit/Integration Tests in Code:** Write automated tests within your Python project using a library like `pytest` and `fastapi.testclient.TestClient` (which can also test WebSockets) to simulate the WebSocket lifecycle and message exchange.

### Example: Conceptual Python WebSocket Client Snippet (for advanced testing)

```python
# import asyncio
# import websockets
# import json
# import base64

# async def test_twilio_websocket():
#     uri = "ws://localhost:8000/ws/media-stream"
#     async with websockets.connect(uri) as websocket:
#         # 1. Send "connected" (server usually initiates, but good to know format)
#         # Server expects to receive "start" from Twilio first after connection

#         # 2. Send "start" message (simulating Twilio)
#         start_message = {
#             "event": "start",
#             "sequenceNumber": "1",
#             "start": {
#                 "accountSid": "ACxxxx",
#                 "streamSid": "MZxxxx", # Important: server will use this
#                 "callSid": "CAxxxx",
#                 "tracks": ["inbound"],
#                 "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}
#             }
#         }
#         await websocket.send(json.dumps(start_message))
#         print(f"> Sent 'start' message with streamSid: {start_message['start']['streamSid']}")

#         # 3. Receive messages from server (e.g., AI's first audio if any)
#         # response = await websocket.recv()
#         # print(f"< Received: {response}")

#         # 4. Send "media" message (simulating audio from Twilio)
#         # (Create dummy mulaw audio, base64 encode it)
#         dummy_mulaw_payload_b64 = base64.b64encode(b"\xff" * 320).decode('utf-8') # 20ms of silence
#         media_message = {
#             "event": "media",
#             "sequenceNumber": "2",
#             "streamSid": start_message['start']['streamSid'],
#             "media": {
#                 "track": "inbound",
#                 "chunk": "1",
#                 "timestamp": "50", # in ms
#                 "payload": dummy_mulaw_payload_b64
#             }
#         }
#         await websocket.send(json.dumps(media_message))
#         print(f"> Sent 'media' message")

#         # Loop to receive audio from AI and potentially send more
#         # while True:
#         #     response_str = await websocket.recv()
#         #     response_json = json.loads(response_str)
#         #     if response_json["event"] == "media":
#         #         print(f"< Received AI audio payload: {response_json['media']['payload'][:30]}...")
#         #     # Add logic to send more media or stop

#         # 5. Send "stop" message
#         # stop_message = {
#         #     "event": "stop",
#         #     "sequenceNumber": "3",
#         #     "streamSid": start_message['start']['streamSid'],
#         #     "stop": {"reason": "caller_hangup"}
#         # }
#         # await websocket.send(json.dumps(stop_message))
#         # print(f"> Sent 'stop' message")

# if __name__ == "__main__":
#     # asyncio.run(test_twilio_websocket())
#     print("Conceptual WebSocket client. Uncomment and adapt to run.")
```

## Conclusion

Testing the HTTP webhook with `curl` is straightforward for verifying TwiML generation and basic request handling. However, for the WebSocket media streaming, more specialized tools or actual end-to-end testing with Twilio is necessary to validate the complex bi-directional audio flow.
