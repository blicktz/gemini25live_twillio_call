# AI Call Answering Service (MVP)

## Overview

This project is a Minimum Viable Product (MVP) of an AI-powered call answering service. It uses FastAPI as the backend framework, integrating with Twilio for telephony services and Google Gemini for conversational AI and speech-to-text/text-to-speech capabilities. The application can receive phone calls, stream audio to Gemini for processing, and stream Gemini's audio responses back to the caller in real time.

## Features

*   **Twilio Voice Integration:** Receives incoming calls via a Twilio phone number.
*   **TwiML Generation:** Dynamically generates TwiML to control call flow, specifically to start bi-directional media streams.
*   **WebSocket Media Streaming:** Handles real-time, bi-directional audio streaming between Twilio and the application.
*   **Google Gemini Integration:** Streams audio to Gemini for AI-driven conversation.
*   **Real-time Audio Processing:**
    *   Decodes MuLaw audio from Twilio to LPCM.
    *   Resamples audio between different rates (8kHz for Twilio, 16kHz input for Gemini, 24kHz output from Gemini).
    *   Encodes LPCM audio to MuLaw for sending back to Twilio.
*   **Basic Barge-in Support:** Allows the caller to interrupt the AI's response.
*   **Configuration Management:** Uses `.env` files for managing sensitive credentials and application settings.
*   **FastAPI Backend:** Modern, asynchronous Python web framework.

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application setup, Uvicorn runner
│   ├── config.py               # Environment variable loading and settings
│   ├── twilio_integration/
│   │   ├── __init__.py
│   │   ├── webhooks.py         # Twilio voice webhook (TwiML generation)
│   │   └── websockets.py       # Twilio media stream WebSocket handler
│   ├── gemini_integration/
│   │   ├── __init__.py
│   │   └── streaming.py        # Gemini API streaming client
│   ├── audio_processing/
│   │   ├── __init__.py
│   │   └── utils.py            # Audio decoding, encoding, resampling
│   └── core/
│       ├── __init__.py
│       └── models.py           # Pydantic models (e.g., for WebSocket messages)
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment variables
└── README.md                   # This file
```

## Prerequisites

*   Python 3.8+
*   A Twilio account with:
    *   Account SID
    *   Auth Token
    *   A Twilio Phone Number capable of voice calls
*   A Google Cloud Project with the Gemini API enabled and an API Key.
*   `ngrok` (or a similar tunneling service) for local development to expose your local server to the internet so Twilio can reach your webhooks.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Create and activate a virtual environment:**
    *   On macOS and Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create and configure your environment file:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and fill in your actual credentials:
        *   `TWILIO_ACCOUNT_SID`
        *   `TWILIO_AUTH_TOKEN`
        *   `TWILIO_PHONE_NUMBER`
        *   `GEMINI_API_KEY`
        *   `BASE_URL` (e.g., your ngrok HTTPS URL like `https://your-unique-id.ngrok.io`)
        *   `TWILIO_REQUEST_VALIDATION_SECRET` (optional, can be a strong unique key you generate if you want to implement more advanced HMAC validation beyond the standard RequestValidator)

## Running the Application

1.  **Start the FastAPI server:**
    You can run the application using the script in `app/main.py`:
    ```bash
    python app/main.py
    ```
    Alternatively, you can use Uvicorn directly (often preferred for more control):
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The server will typically run on `http://localhost:8000`.

2.  **Expose your local server with ngrok:**
    If running locally, start ngrok to tunnel HTTP traffic to your local server's port (e.g., 8000):
    ```bash
    ngrok http 8000
    ```
    Note the HTTPS forwarding URL provided by ngrok (e.g., `https://<unique-id>.ngrok.io`).

3.  **Update `BASE_URL` in `.env`:**
    Ensure the `BASE_URL` in your `.env` file matches your ngrok HTTPS URL. The application uses this to construct WebSocket URLs for Twilio. Restart the FastAPI application if you change `.env` for it to take effect.

## Twilio Configuration

1.  Log in to your [Twilio Console](https://www.twilio.com/console).
2.  Navigate to "Phone Numbers" -> "Manage" -> "Active Numbers".
3.  Select the Twilio phone number you wish to use for this service.
4.  Scroll down to the "Voice & Fax" section.
5.  For "A CALL COMES IN", select "Webhook".
6.  Set the webhook URL to `YOUR_NGROK_URL/api/twilio-voice`. For example, if your ngrok URL is `https://abcdef123456.ngrok.io`, the webhook URL will be `https://abcdef123456.ngrok.io/api/twilio-voice`.
7.  Ensure the HTTP method is set to `HTTP POST`.
8.  Save the configuration.

## How it Works

1.  **Incoming Call:** A user calls your configured Twilio phone number.
2.  **Twilio Webhook:** Twilio sends an HTTP POST request to the `/api/twilio-voice` endpoint of your application.
3.  **TwiML Response:** The application responds with TwiML (Twilio Markup Language) instructing Twilio to `<Start><Stream>` a bi-directional media stream to the application's WebSocket endpoint (`/ws/media-stream`).
4.  **WebSocket Connection:** Twilio establishes a WebSocket connection with your server.
5.  **Audio Streaming & Processing:**
    *   **Twilio to App:** Twilio streams the caller's audio (8kHz MuLaw) over the WebSocket. The application:
        *   Receives the audio data.
        *   Decodes it from base64.
        *   Converts MuLaw to LPCM (16-bit, 8kHz).
        *   Resamples LPCM from 8kHz to 16kHz (suitable for Gemini).
        *   Sends the 16kHz LPCM audio to the Gemini API.
    *   **Gemini to App:** The Gemini API processes the audio and streams back its spoken response (LPCM 16-bit, 24kHz). The application:
        *   Receives Gemini's audio data.
        *   Resamples LPCM from 24kHz to 8kHz.
        *   Encodes 8kHz LPCM to MuLaw.
        *   Encodes MuLaw audio to base64.
        *   Sends this base64 encoded audio payload back to Twilio over the WebSocket as a `media` message.
6.  **Caller Hears Response:** Twilio plays the received audio stream back to the caller.
7.  **Call Termination:** When the call ends, Twilio sends a `stop` message over the WebSocket, and the session is cleaned up.

## Environment Variables

The following environment variables are used by the application and should be defined in your `.env` file:

*   `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
*   `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token (used for validating Twilio requests and API calls).
*   `TWILIO_PHONE_NUMBER`: Your Twilio phone number that will be used for the service.
*   `BASE_URL`: The public base URL where your application is accessible (e.g., `https://your-ngrok-id.ngrok.io`). This is crucial for Twilio to connect to your WebSocket.
*   `GEMINI_API_KEY`: Your API key for the Google Gemini API.
*   `LOG_LEVEL`: The logging level for the application (e.g., `INFO`, `DEBUG`, `WARNING`). Defaults to `INFO`.
*   `TWILIO_REQUEST_VALIDATION_SECRET`: A secret key you can define for enhanced HMAC validation of Twilio webhook requests. The current implementation primarily uses `TWILIO_AUTH_TOKEN` with `RequestValidator`. This variable is available if custom validation logic is preferred.

## Limitations / MVP Scope

This is an MVP and has several limitations:

*   **No Database/Persistence:** Call history, transcripts, or user data are not stored.
*   **No Call Recording:** The application does not record calls.
*   **Basic Error Handling:** While some error handling is in place, it could be more robust for production scenarios.
*   **Simplified Barge-In:** Barge-in (caller interrupting the AI) is implemented by cancelling the AI's current audio generation task. More sophisticated handling might be needed for complex interactions.
*   **No Advanced Call Management:** Features like call transfers, queuing, or complex IVR trees are not included.
*   **Single Model Focus:** Primarily designed for conversational interaction with Gemini.
*   **Security:** Request validation is implemented, but for a production system, review all security aspects (dependencies, rate limiting, etc.).
```
