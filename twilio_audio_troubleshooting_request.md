# Twilio WebSocket Audio Playback Issue - Need Help

## What We Implemented

We refactored a Twilio WebSocket media streaming integration to play pre-recorded audio files during phone calls. Here's what we built:

### Audio Processing Pipeline
1. **WebSocket Handler**: Handles Twilio media stream events (start, media, stop)
2. **Audio File Processing**: Reads μ-law encoded WAV files (8kHz, mono, format 7)
3. **Chunked Playback**: Splits audio into 100ms chunks for streaming
4. **Queue-based Delivery**: Uses asyncio queue to send audio data to Twilio

### Technical Implementation Details

**Audio File Format:**
- Source: μ-law encoded WAV file created with: `ffmpeg -i input.mp3 -f wav -acodec pcm_mulaw -ar 8000 -ac 1 output.wav`
- Format: 8kHz sample rate, mono channel, μ-law encoding (WAV format 7)
- Duration: Limited to first 10 seconds for testing

**Key Methods:**
1. `_play_sample_audio()` - Main entry point, detects WAV format and routes appropriately
2. `_play_raw_mulaw_audio()` - Handles μ-law WAV files by reading raw binary data
3. `_send_mulaw_to_twilio()` - Sends μ-law data directly to Twilio via WebSocket

**Audio Processing Flow:**
```
Call Connects → _handle_stream_start() → _play_sample_audio() → 
_play_raw_mulaw_audio() → Read WAV file → Skip header → 
Limit to 10 seconds → Split into 100ms chunks → 
_send_mulaw_to_twilio() → Base64 encode → Queue for WebSocket delivery
```

**Message Format Sent to Twilio:**
```json
{
  "event": "media",
  "streamSid": "stream_sid_here",
  "media": {"payload": "base64_encoded_mulaw_data"}
}
```

## The Problem

**Issue**: No audio is heard during Twilio phone calls, despite successful WebSocket connection and message delivery.

**What We Observe:**
- WebSocket connects successfully
- Stream start event is received and handled
- Audio file is read and processed correctly
- Messages are queued and sent to Twilio WebSocket
- No errors in logs
- But no audio is heard on the phone call

## Code Structure

**WebSocket Event Handling:**
```python
async def _handle_stream_start(self, msg: TwilioMediaMessage):
    # Triggered when Twilio call connects
    await self._play_sample_audio()  # Start audio playback

async def _play_raw_mulaw_audio(self, wav_path: str):
    # Read μ-law WAV file, limit to 10 seconds
    # Split into 100ms chunks (800 bytes each at 8kHz)
    # Send each chunk via _send_mulaw_to_twilio()

async def _send_mulaw_to_twilio(self, mulaw_data: bytes):
    # Convert μ-law bytes to base64
    # Create Twilio media message
    # Queue for WebSocket delivery
```

## Questions for Troubleshooting

1. **Audio Format**: Is our μ-law encoding correct for Twilio? Should we be using a different format?

2. **Timing**: Do we need to wait for a specific event before sending audio, or add delays between chunks?

3. **Message Structure**: Is our Twilio media message format correct? Are we missing any required fields?

4. **WebSocket State**: Should we verify specific WebSocket states before sending audio?

5. **Audio Headers**: Are we correctly skipping the WAV header when reading μ-law data?

6. **Chunk Size**: Is 100ms (800 bytes at 8kHz) the right chunk size for Twilio?

7. **Base64 Encoding**: Is our base64 encoding of μ-law data correct?

## Environment Details

- **Platform**: Python FastAPI application
- **Twilio Integration**: WebSocket media streaming
- **Audio Processing**: Custom implementation with asyncio queues
- **File Format**: μ-law WAV (created with ffmpeg)
- **Sample Rate**: 8kHz mono

## Request for Help

We need assistance identifying why audio isn't being heard during Twilio calls despite successful message delivery. Any insights into:
- Proper Twilio audio message formatting
- Required timing or sequencing
- Audio format requirements
- Common pitfalls in Twilio media streaming

Would be greatly appreciated!