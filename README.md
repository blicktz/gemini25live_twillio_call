# AI Call Answering Service

A FastAPI-based backend application that integrates Twilio for voice telephony with Google's Gemini API for real-time, full-duplex conversational AI. This service enables AI-powered call answering with natural voice interactions.

## Features

- **Real-time Voice Processing**: Handles incoming calls via Twilio webhooks
- **AI-Powered Conversations**: Uses Gemini API for natural language processing and text-to-speech
- **Full-Duplex Audio**: Supports real-time bidirectional audio streaming
- **Low-Latency Audio Processing**: Efficient audio format conversion and resampling
- **WebSocket Communication**: Real-time audio streaming between Twilio and Gemini
- **Async Architecture**: Built with FastAPI for high concurrency

## Architecture

```
Twilio Call → Webhook → FastAPI → WebSocket → Audio Processing → Gemini API
                ↓                      ↑
            TwiML Response         Audio Response
```

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app initialization and main entry point
│   ├── config.py               # Configuration loading (from .env)
│   ├── twilio_integration/
│   │   ├── __init__.py
│   │   ├── webhooks.py         # Twilio voice webhook endpoint
│   │   └── websockets.py       # WebSocket handler for Twilio media stream
│   ├── gemini_integration/
│   │   ├── __init__.py
│   │   └── streaming.py        # Gemini API streaming client logic
│   ├── audio_processing/
│   │   ├── __init__.py
│   │   └── utils.py            # Audio transcoding and resampling utilities
│   └── core/
│       ├── __init__.py
│       └── models.py           # Pydantic models for request/response
├── requirements.txt            # Python dependencies
├── .env.example               # Example environment variables
└── README.md                  # This file
```

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Twilio account with phone number
- Google AI API key for Gemini
- Public URL for webhooks (ngrok recommended for development)

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd twillio_gemini25

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your credentials
nano .env  # or use your preferred editor
```

Required environment variables:

- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
- `GEMINI_API_KEY`: Your Google AI API key
- `TWILIO_WEBHOOK_URL`: Your public webhook URL (optional)

### 3. Get Required API Keys

#### Twilio Setup
1. Sign up at [Twilio Console](https://console.twilio.com/)
2. Get your Account SID and Auth Token from the dashboard
3. Purchase a phone number for incoming calls

#### Gemini API Setup
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the API key to your `.env` file

### 4. Running the Application

#### Development Mode

```bash
# Run with auto-reload
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Production Mode

```bash
# Set DEBUG=false in .env first
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Expose Your Local Server (Development)

For development, use ngrok to expose your local server:

```bash
# Install ngrok: https://ngrok.com/download
# Run ngrok in another terminal
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update TWILIO_WEBHOOK_URL in .env if needed
```

### 6. Configure Twilio Webhook

1. Go to your Twilio Console
2. Navigate to Phone Numbers → Manage → Active numbers
3. Click on your phone number
4. Set the webhook URL for incoming calls:
   ```
   https://your-domain.com/api/v1/twilio-voice
   ```
   (Replace with your actual domain or ngrok URL)

## API Endpoints

### HTTP Endpoints

- `GET /` - Root endpoint (health check)
- `GET /health` - Health check endpoint
- `POST /api/v1/twilio-voice` - Twilio voice webhook
- `POST /api/v1/twilio-status` - Call status updates

### WebSocket Endpoints

- `WS /ws/media-stream` - Twilio media stream handler

## Audio Processing Pipeline

1. **Incoming Audio (Twilio → Gemini)**:
   - Receive: 8kHz MuLaw (base64 encoded)
   - Decode: Base64 → Raw MuLaw bytes
   - Convert: MuLaw → 16-bit PCM
   - Resample: 8kHz → 16kHz
   - Send to Gemini API

2. **Outgoing Audio (Gemini → Twilio)**:
   - Receive: 24kHz 16-bit PCM from Gemini
   - Resample: 24kHz → 8kHz
   - Convert: 16-bit PCM → MuLaw
   - Encode: Base64
   - Send to Twilio via WebSocket

## Testing

1. Start the application
2. Call your Twilio phone number
3. You should hear: "Hello! Please wait while I connect you to our AI assistant."
4. The call will be connected to the AI assistant
5. Speak naturally - the AI should respond

## Troubleshooting

### Common Issues

1. **Webhook not receiving calls**:
   - Check that your webhook URL is publicly accessible
   - Verify the URL is correctly configured in Twilio Console
   - Check server logs for incoming requests

2. **Audio quality issues**:
   - Verify sample rates in configuration
   - Check network latency and bandwidth
   - Monitor logs for audio processing errors

3. **Gemini API errors**:
   - Verify API key is correct and has proper permissions
   - Check API quotas and rate limits
   - Monitor logs for API response errors

### Logging

The application logs important events:
- Call start/end events
- WebSocket connections/disconnections
- Audio processing pipeline
- API errors and responses

Logs are output to console. For production, consider using structured logging.

## Production Considerations

1. **Security**:
   - Enable Twilio signature validation
   - Use HTTPS for all endpoints
   - Secure API keys and tokens
   - Implement rate limiting

2. **Scalability**:
   - Use multiple worker processes
   - Implement connection pooling
   - Consider load balancing
   - Monitor resource usage

3. **Monitoring**:
   - Set up health checks
   - Monitor API quotas
   - Track call metrics
   - Implement alerting

## Development Notes

- The Gemini integration includes simulation code for development
- Replace simulation methods with actual Gemini API calls for production
- Audio processing uses Python's built-in `audioop` for minimal dependencies
- Consider `pydub` for more advanced audio processing needs

## License

MIT License - see LICENSE file for details