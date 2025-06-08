"""Audio processing utilities for format conversion and resampling."""

import audioop
import base64
import logging
import wave
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Handles audio format conversion and resampling for low-latency processing."""
    
    @staticmethod
    def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
        """Convert MuLaw audio data to 16-bit PCM.
        
        Args:
            mulaw_data: Raw MuLaw audio bytes
            
        Returns:
            16-bit PCM audio bytes
        """
        try:
            # Convert MuLaw to 16-bit PCM
            pcm_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes per sample (16-bit)
            return pcm_data
        except Exception as e:
            logger.error(f"Error converting MuLaw to PCM: {e}")
            raise
    
    @staticmethod
    def pcm_to_mulaw(pcm_data: bytes) -> bytes:
        """Convert 16-bit PCM audio data to MuLaw.
        
        Args:
            pcm_data: 16-bit PCM audio bytes
            
        Returns:
            MuLaw audio bytes
        """
        try:
            # Convert 16-bit PCM to MuLaw
            mulaw_data = audioop.lin2ulaw(pcm_data, 2)  # 2 bytes per sample (16-bit)
            return mulaw_data
        except Exception as e:
            logger.error(f"Error converting PCM to MuLaw: {e}")
            raise
    
    @staticmethod
    def resample_audio(audio_data: bytes, from_rate: int, to_rate: int, sample_width: int = 2) -> bytes:
        """Resample audio data from one sample rate to another.
        
        Args:
            audio_data: Raw audio bytes
            from_rate: Source sample rate (Hz)
            to_rate: Target sample rate (Hz)
            sample_width: Bytes per sample (2 for 16-bit)
            
        Returns:
            Resampled audio bytes
        """
        try:
            if from_rate == to_rate:
                return audio_data
            
            # Use audioop for resampling
            resampled_data, _ = audioop.ratecv(
                audio_data, sample_width, 1, from_rate, to_rate, None
            )
            return resampled_data
        except Exception as e:
            logger.error(f"Error resampling audio from {from_rate}Hz to {to_rate}Hz: {e}")
            raise
    
    @staticmethod
    def decode_base64_audio(base64_audio: str) -> bytes:
        """Decode base64 encoded audio data.
        
        Args:
            base64_audio: Base64 encoded audio string
            
        Returns:
            Raw audio bytes
        """
        try:
            return base64.b64decode(base64_audio)
        except Exception as e:
            logger.error(f"Error decoding base64 audio: {e}")
            raise
    
    @staticmethod
    def encode_base64_audio(audio_data: bytes) -> str:
        """Encode audio data to base64 string.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Base64 encoded audio string
        """
        try:
            return base64.b64encode(audio_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding audio to base64: {e}")
            raise
    
    @staticmethod
    def save_audio_as_wav(audio_data: bytes, sample_rate: int, filename: str, sample_width: int = 2, channels: int = 1):
        """Save PCM audio data as a WAV file.
        
        Args:
            audio_data: Raw PCM audio bytes
            sample_rate: Sample rate in Hz
            filename: Output filename (will be created in debug_audio directory)
            sample_width: Bytes per sample (2 for 16-bit)
            channels: Number of audio channels (1 for mono)
        """
        try:
            # Create debug_audio directory if it doesn't exist
            debug_dir = Path("debug_audio")
            debug_dir.mkdir(exist_ok=True)
            
            # Add timestamp to filename for uniqueness
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
            wav_filename = debug_dir / f"{timestamp}_{filename}"
            
            with wave.open(str(wav_filename), 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)
            
            logger.debug(f"DEBUG: Saved audio to {wav_filename} ({len(audio_data)} bytes, {sample_rate}Hz)")
            return str(wav_filename)
            
        except Exception as e:
            logger.error(f"Error saving audio as WAV: {e}")
            raise
    
    @staticmethod
    def save_mulaw_as_wav(mulaw_data: bytes, sample_rate: int, filename: str):
        """Convert MuLaw audio to PCM and save as WAV file.
        
        Args:
            mulaw_data: Raw MuLaw audio bytes
            sample_rate: Sample rate in Hz
            filename: Output filename
        """
        try:
            # Convert MuLaw to PCM first
            pcm_data = AudioProcessor.mulaw_to_pcm(mulaw_data)
            
            # Save as WAV
            return AudioProcessor.save_audio_as_wav(pcm_data, sample_rate, f"mulaw_{filename}")
            
        except Exception as e:
            logger.error(f"Error saving MuLaw audio as WAV: {e}")
            raise
    
    def process_twilio_to_gemini(self, base64_mulaw: str, input_rate: int = 8000, output_rate: int = 16000) -> bytes:
        """Convert Twilio audio (base64 MuLaw) to Gemini format (16kHz PCM).
        
        Args:
            base64_mulaw: Base64 encoded MuLaw audio from Twilio
            input_rate: Input sample rate (typically 8kHz from Twilio)
            output_rate: Output sample rate (16kHz for Gemini)
            
        Returns:
            16-bit PCM audio bytes at target sample rate
        """
        try:
            # Decode base64 to get raw MuLaw bytes
            mulaw_data = self.decode_base64_audio(base64_mulaw)
            
            # Convert MuLaw to 16-bit PCM
            pcm_data = self.mulaw_to_pcm(mulaw_data)
            
            # Resample from input rate to output rate
            resampled_pcm = self.resample_audio(pcm_data, input_rate, output_rate)
            
            return resampled_pcm
        except Exception as e:
            logger.error(f"Error processing Twilio to Gemini audio: {e}")
            raise
    
    def process_gemini_to_twilio(self, pcm_data: bytes, input_rate: int = 24000, output_rate: int = 8000, save_debug_audio: bool = True) -> str:
        """Convert Gemini audio (24kHz PCM) to Twilio format (base64 MuLaw).
        
        Args:
            pcm_data: 16-bit PCM audio bytes from Gemini
            input_rate: Input sample rate (typically 24kHz from Gemini)
            output_rate: Output sample rate (8kHz for Twilio)
            save_debug_audio: Whether to save debug audio files
            
        Returns:
            Base64 encoded MuLaw audio string for Twilio
        """
        try:
            logger.debug(f"DEBUG: process_gemini_to_twilio - input: {len(pcm_data)} bytes, {input_rate}Hz -> {output_rate}Hz")
            
            # Save original Gemini audio for debugging
            if save_debug_audio:
                try:
                    self.save_audio_as_wav(pcm_data, input_rate, f"gemini_original_{input_rate}hz.wav")
                except Exception as e:
                    logger.warning(f"Failed to save original Gemini audio: {e}")
            
            # Resample from input rate to output rate
            resampled_pcm = self.resample_audio(pcm_data, input_rate, output_rate)
            logger.debug(f"DEBUG: Resampled to {len(resampled_pcm)} bytes")
            
            # Save resampled audio for debugging
            if save_debug_audio:
                try:
                    self.save_audio_as_wav(resampled_pcm, output_rate, f"resampled_{output_rate}hz.wav")
                except Exception as e:
                    logger.warning(f"Failed to save resampled audio: {e}")
            
            # Convert PCM to MuLaw
            mulaw_data = self.pcm_to_mulaw(resampled_pcm)
            logger.debug(f"DEBUG: Converted to MuLaw: {len(mulaw_data)} bytes")
            
            # Save MuLaw audio as WAV for debugging (converted back to PCM for playback)
            if save_debug_audio:
                try:
                    self.save_mulaw_as_wav(mulaw_data, output_rate, f"final_mulaw_{output_rate}hz.wav")
                except Exception as e:
                    logger.warning(f"Failed to save MuLaw audio: {e}")
            
            # Encode to base64
            base64_mulaw = self.encode_base64_audio(mulaw_data)
            logger.debug(f"DEBUG: Base64 encoded: {len(base64_mulaw)} characters")
            
            return base64_mulaw
        except Exception as e:
            logger.error(f"Error processing Gemini to Twilio audio: {e}")
            raise


# Global audio processor instance
audio_processor = AudioProcessor()