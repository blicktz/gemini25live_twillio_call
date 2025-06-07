"""
Test Phase 3: Audio Sending to ADK
Tests the audio sending functionality of the GeminiStreamingClient.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.gemini_integration.streaming import GeminiStreamingClient


class TestADKPhase3:
    """Test Phase 3: Audio Sending to ADK"""

    @pytest_asyncio.fixture
    async def client(self):
        """Create a GeminiStreamingClient instance for testing."""
        client = GeminiStreamingClient()
        yield client
        # Cleanup
        if client.is_active:
            await client.stop_session()

    @pytest.mark.asyncio
    async def test_send_audio_chunk_when_active(self, client):
        """Test that audio chunks are queued when session is active."""
        # Mock the session as active
        client.is_active = True
        
        # Test data
        test_audio = b"test_audio_data_16khz_lpcm16"
        
        # Send audio chunk
        await client.send_audio_chunk(test_audio)
        
        # Verify audio was queued
        assert not client._audio_send_queue.empty()
        queued_audio = await client._audio_send_queue.get()
        assert queued_audio == test_audio

    @pytest.mark.asyncio
    async def test_send_audio_chunk_when_inactive(self, client):
        """Test that audio chunks are ignored when session is inactive."""
        # Ensure session is inactive
        client.is_active = False
        
        # Test data
        test_audio = b"test_audio_data"
        
        # Send audio chunk
        await client.send_audio_chunk(test_audio)
        
        # Verify audio was not queued
        assert client._audio_send_queue.empty()

    @pytest.mark.asyncio
    async def test_send_empty_audio_chunk(self, client):
        """Test that empty audio chunks are ignored."""
        client.is_active = True
        
        # Send empty audio chunk
        await client.send_audio_chunk(b"")
        
        # Verify nothing was queued
        assert client._audio_send_queue.empty()

    @pytest.mark.asyncio
    async def test_send_none_audio_chunk(self, client):
        """Test that None audio chunks are ignored."""
        client.is_active = True
        
        # Send None audio chunk
        await client.send_audio_chunk(None)
        
        # Verify nothing was queued
        assert client._audio_send_queue.empty()

    @pytest.mark.asyncio
    async def test_adk_send_loop_processes_audio(self, client):
        """Test that the ADK send loop processes queued audio."""
        # Mock ADK components
        mock_live_request_queue = AsyncMock()
        client.live_request_queue = mock_live_request_queue
        client.is_active = True
        
        # Add test audio to queue
        test_audio = b"test_audio_data_16khz_lpcm16"
        await client._audio_send_queue.put(test_audio)
        
        # Start the send loop task
        send_task = asyncio.create_task(client._send_adk_loop())
        
        # Give it a moment to process
        await asyncio.sleep(0.1)
        
        # Stop the loop
        client.is_active = False
        
        # Wait for task to complete
        try:
            await asyncio.wait_for(send_task, timeout=1.0)
        except asyncio.TimeoutError:
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
        
        # Verify send_realtime was called
        mock_live_request_queue.send_realtime.assert_called_once()
        
        # Verify the call was made with correct parameters
        call_args = mock_live_request_queue.send_realtime.call_args
        blob = call_args[0][0]  # First positional argument
        assert blob.data == test_audio
        assert blob.mime_type == "audio/pcm"

    @pytest.mark.asyncio
    async def test_adk_send_loop_handles_send_errors(self, client):
        """Test that the ADK send loop handles send errors gracefully."""
        # Mock ADK components with error
        mock_live_request_queue = AsyncMock()
        mock_live_request_queue.send_realtime.side_effect = Exception("Send error")
        client.live_request_queue = mock_live_request_queue
        client.is_active = True
        
        # Add test audio to queue
        test_audio = b"test_audio_data"
        await client._audio_send_queue.put(test_audio)
        
        # Start the send loop task
        send_task = asyncio.create_task(client._send_adk_loop())
        
        # Give it a moment to process
        await asyncio.sleep(0.1)
        
        # Stop the loop
        client.is_active = False
        
        # Wait for task to complete
        try:
            await asyncio.wait_for(send_task, timeout=1.0)
        except asyncio.TimeoutError:
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
        
        # Verify send_realtime was called despite error
        mock_live_request_queue.send_realtime.assert_called_once()
        
        # Verify task_done was still called (queue should be processed)
        assert client._audio_send_queue.empty()

    @pytest.mark.asyncio
    async def test_adk_send_loop_timeout_behavior(self, client):
        """Test that the ADK send loop handles timeouts correctly."""
        client.is_active = True
        client.live_request_queue = AsyncMock()
        
        # Start the send loop task
        send_task = asyncio.create_task(client._send_adk_loop())
        
        # Let it run for a bit (should timeout waiting for audio)
        await asyncio.sleep(1.5)  # Longer than the 1.0 second timeout
        
        # Stop the loop
        client.is_active = False
        
        # Wait for task to complete
        try:
            await asyncio.wait_for(send_task, timeout=2.0)
        except asyncio.TimeoutError:
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
        
        # Should complete without errors (no audio was sent)
        assert not send_task.done() or not send_task.exception()

    @pytest.mark.asyncio
    async def test_multiple_audio_chunks_processed_sequentially(self, client):
        """Test that multiple audio chunks are processed in order."""
        # Mock ADK components
        mock_live_request_queue = AsyncMock()
        client.live_request_queue = mock_live_request_queue
        client.is_active = True
        
        # Add multiple test audio chunks to queue
        test_audio_chunks = [
            b"audio_chunk_1",
            b"audio_chunk_2", 
            b"audio_chunk_3"
        ]
        
        for chunk in test_audio_chunks:
            await client._audio_send_queue.put(chunk)
        
        # Start the send loop task
        send_task = asyncio.create_task(client._send_adk_loop())
        
        # Give it time to process all chunks
        await asyncio.sleep(0.2)
        
        # Stop the loop
        client.is_active = False
        
        # Wait for task to complete
        try:
            await asyncio.wait_for(send_task, timeout=1.0)
        except asyncio.TimeoutError:
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
        
        # Verify all chunks were sent
        assert mock_live_request_queue.send_realtime.call_count == 3
        
        # Verify chunks were sent in order
        calls = mock_live_request_queue.send_realtime.call_args_list
        for i, call in enumerate(calls):
            blob = call[0][0]
            assert blob.data == test_audio_chunks[i]
            assert blob.mime_type == "audio/pcm"


if __name__ == "__main__":
    pytest.main([__file__])