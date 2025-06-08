"""
Test Phase 4: Audio & Text Receiving from ADK
Tests the enhanced _process_agent_events_loop implementation.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_audio_processor():
    """Mock audio processor for testing."""
    with patch('app.audio_processing.utils.audio_processor') as mock:
        # Mock the audio processing methods
        mock.resample_audio.return_value = b'resampled_audio_data'
        mock.pcm_to_mulaw.return_value = b'mulaw_audio_data'
        yield mock


@pytest.fixture
def mock_event_with_audio():
    """Create a mock ADK event with audio content."""
    event = MagicMock()
    event.turn_complete = False
    event.interrupted = False
    
    # Create mock content with audio part
    event.content = MagicMock()
    audio_part = MagicMock()
    audio_part.inline_data = MagicMock()
    audio_part.inline_data.mime_type = "audio/pcm"
    # Create fake audio data that's a multiple of 2 bytes (16-bit samples)
    audio_part.inline_data.data = b'\x00\x01' * 480  # 480 samples = 20ms at 24kHz
    audio_part.text = None
    
    event.content.parts = [audio_part]
    return event


@pytest.fixture
def mock_event_with_text():
    """Create a mock ADK event with text content."""
    event = MagicMock()
    event.turn_complete = False
    event.interrupted = False
    
    # Create mock content with text part
    event.content = MagicMock()
    text_part = MagicMock()
    text_part.inline_data = None
    text_part.text = "Hello, this is a test transcription"
    
    event.content.parts = [text_part]
    return event


@pytest.fixture
def mock_event_turn_complete():
    """Create a mock ADK event for turn completion."""
    event = MagicMock()
    event.turn_complete = True
    event.interrupted = False
    event.content = None
    return event


@pytest.mark.asyncio
async def test_process_audio_part(mock_audio_processor):
    """Test processing of audio content from ADK events."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    
    # Set up mock audio callback
    audio_callback = AsyncMock()
    text_callback = AsyncMock()
    client.set_callbacks(audio_callback, text_callback)
    
    # Create mock audio part
    audio_part = MagicMock()
    audio_part.inline_data = MagicMock()
    audio_part.inline_data.mime_type = "audio/pcm"
    audio_part.inline_data.data = b'\x00\x01' * 480  # 480 samples = 20ms at 24kHz
    
    # Test audio processing
    await client._process_audio_part(audio_part)
    
    # Verify audio processor was called correctly
    mock_audio_processor.resample_audio.assert_called_once_with(
        b'\x00\x01' * 480,
        from_rate=24000,
        to_rate=8000,
        sample_width=2
    )
    mock_audio_processor.pcm_to_mulaw.assert_called_once_with(b'resampled_audio_data')
    
    # Verify audio callback was called
    audio_callback.assert_called_once_with(b'mulaw_audio_data')


@pytest.mark.asyncio
async def test_process_text_part():
    """Test processing of text content from ADK events."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    
    # Set up mock callbacks
    audio_callback = AsyncMock()
    text_callback = AsyncMock()
    client.set_callbacks(audio_callback, text_callback)
    
    # Create mock text part
    text_part = MagicMock()
    text_part.text = "  Hello, this is a test transcription  "
    
    # Test text processing
    await client._process_text_part(text_part)
    
    # Verify text callback was called with stripped text
    text_callback.assert_called_once_with("Hello, this is a test transcription")


@pytest.mark.asyncio
async def test_process_event_content_parts_mixed(mock_audio_processor):
    """Test processing of event with both audio and text parts."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    
    # Set up mock callbacks
    audio_callback = AsyncMock()
    text_callback = AsyncMock()
    client.set_callbacks(audio_callback, text_callback)
    
    # Create mock parts with both audio and text
    audio_part = MagicMock()
    audio_part.inline_data = MagicMock()
    audio_part.inline_data.mime_type = "audio/pcm"
    audio_part.inline_data.data = b'\x00\x01' * 480  # Valid audio data
    audio_part.text = None
    
    text_part = MagicMock()
    text_part.inline_data = None
    text_part.text = "Test transcription"
    
    parts = [audio_part, text_part]
    
    # Test processing both parts
    await client._process_event_content_parts(parts)
    
    # Verify both callbacks were called
    audio_callback.assert_called_once()
    text_callback.assert_called_once_with("Test transcription")


@pytest.mark.asyncio
async def test_process_agent_events_loop_with_audio_event(mock_audio_processor, mock_event_with_audio):
    """Test the main event processing loop with audio events."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    client.is_active = True
    
    # Set up mock callbacks
    audio_callback = AsyncMock()
    text_callback = AsyncMock()
    client.set_callbacks(audio_callback, text_callback)
    
    # Create mock live_events async iterator
    async def mock_live_events():
        yield mock_event_with_audio
        # Simulate end of stream
        client.is_active = False
    
    client.live_events = mock_live_events()
    
    # Test the event processing loop
    await client._process_agent_events_loop()
    
    # Verify audio processing occurred
    mock_audio_processor.resample_audio.assert_called_once()
    mock_audio_processor.pcm_to_mulaw.assert_called_once()
    audio_callback.assert_called_once()


@pytest.mark.asyncio
async def test_process_agent_events_loop_with_text_event(mock_event_with_text):
    """Test the main event processing loop with text events."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    client.is_active = True
    
    # Set up mock callbacks
    audio_callback = AsyncMock()
    text_callback = AsyncMock()
    client.set_callbacks(audio_callback, text_callback)
    
    # Create mock live_events async iterator
    async def mock_live_events():
        yield mock_event_with_text
        # Simulate end of stream
        client.is_active = False
    
    client.live_events = mock_live_events()
    
    # Test the event processing loop
    await client._process_agent_events_loop()
    
    # Verify text processing occurred
    text_callback.assert_called_once_with("Hello, this is a test transcription")


@pytest.mark.asyncio
async def test_process_agent_events_loop_with_turn_complete(mock_event_turn_complete):
    """Test the main event processing loop with turn completion events."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    client.is_active = True
    
    # Create mock live_events async iterator
    async def mock_live_events():
        yield mock_event_turn_complete
        # Simulate end of stream
        client.is_active = False
    
    client.live_events = mock_live_events()
    
    # Test the event processing loop with logging capture
    with patch('app.gemini_integration.streaming.logger') as mock_logger:
        await client._process_agent_events_loop()
        
        # Verify turn complete was logged
        mock_logger.info.assert_any_call("ADK: Turn complete")


@pytest.mark.asyncio
async def test_audio_processing_error_handling(mock_audio_processor):
    """Test error handling in audio processing."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance
    client = GeminiStreamingClient()
    
    # Set up mock callbacks
    audio_callback = AsyncMock()
    text_callback = AsyncMock()
    client.set_callbacks(audio_callback, text_callback)
    
    # Make audio processor raise an exception
    mock_audio_processor.resample_audio.side_effect = Exception("Resampling failed")
    
    # Create mock audio part
    audio_part = MagicMock()
    audio_part.inline_data = MagicMock()
    audio_part.inline_data.mime_type = "audio/pcm"
    audio_part.inline_data.data = b'\x00\x01' * 480  # Valid audio data
    
    # Test that error is handled gracefully
    with patch('app.gemini_integration.streaming.logger') as mock_logger:
        await client._process_audio_part(audio_part)
        
        # Verify error was logged
        mock_logger.error.assert_called()
        
        # Verify callback was not called due to error
        audio_callback.assert_not_called()


@pytest.mark.asyncio
async def test_no_callbacks_set():
    """Test behavior when no callbacks are set."""
    from app.gemini_integration.streaming import GeminiStreamingClient
    
    # Create client instance without setting callbacks
    client = GeminiStreamingClient()
    
    # Create mock audio part
    audio_part = MagicMock()
    audio_part.inline_data = MagicMock()
    audio_part.inline_data.mime_type = "audio/pcm"
    audio_part.inline_data.data = b'\x00\x01' * 480  # Valid audio data
    
    # Create mock text part
    text_part = MagicMock()
    text_part.text = "Test text"
    
    # Test that processing works without callbacks (should log warnings)
    with patch('app.gemini_integration.streaming.logger') as mock_logger:
        await client._process_audio_part(audio_part)
        await client._process_text_part(text_part)
        
        # Verify warnings were logged
        mock_logger.warning.assert_any_call("No audio output callback set")
        mock_logger.debug.assert_any_call("No text output callback set")


if __name__ == "__main__":
    # Run a simple test
    async def simple_test():
        print("Running Phase 4 simple test...")
        
        from app.gemini_integration.streaming import GeminiStreamingClient
        
        # Create client
        client = GeminiStreamingClient()
        
        # Test callback setting
        async def dummy_audio_callback(audio_data):
            print(f"Audio callback received: {len(audio_data)} bytes")
        
        async def dummy_text_callback(text_data):
            print(f"Text callback received: {text_data}")
        
        client.set_callbacks(dummy_audio_callback, dummy_text_callback)
        
        print("Phase 4 implementation test completed successfully!")
    
    asyncio.run(simple_test())