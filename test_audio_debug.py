#!/usr/bin/env python3
"""
Test script to verify audio debugging functionality.
This script tests the audio processing pipeline and WAV file generation.
"""

import os
import sys
import numpy as np
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from audio_processing.utils import AudioProcessor
from config import settings

def generate_test_audio(sample_rate: int = 24000, duration: float = 2.0, frequency: float = 440.0) -> bytes:
    """Generate a test sine wave audio signal."""
    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Generate sine wave (A4 note at 440 Hz)
    wave = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    wave_16bit = (wave * 32767).astype(np.int16)
    
    # Convert to bytes
    return wave_16bit.tobytes()

def test_audio_processing():
    """Test the audio processing pipeline with debug audio saving."""
    print("Testing audio processing with debug audio saving...")
    
    # Create audio processor
    processor = AudioProcessor()
    
    # Generate test audio (24kHz PCM, 2 seconds, 440Hz sine wave)
    print("Generating test audio (24kHz, 2 seconds, 440Hz sine wave)...")
    test_audio = generate_test_audio(sample_rate=24000, duration=2.0, frequency=440.0)
    print(f"Generated {len(test_audio)} bytes of test audio")
    
    # Process audio with debug saving enabled
    print("Processing audio through Gemini->Twilio pipeline...")
    try:
        base64_result = processor.process_gemini_to_twilio(
            pcm_data=test_audio,
            input_rate=24000,
            output_rate=8000,
            save_debug_audio=True
        )
        print(f"Successfully processed audio. Base64 result length: {len(base64_result)} characters")
        
        # Check if debug files were created
        debug_dir = Path("debug_audio")
        if debug_dir.exists():
            print(f"\nDebug audio files created in {debug_dir}:")
            for wav_file in debug_dir.glob("*.wav"):
                file_size = wav_file.stat().st_size
                print(f"  - {wav_file.name}: {file_size} bytes")
        else:
            print("Warning: debug_audio directory was not created")
            
    except Exception as e:
        print(f"Error during audio processing: {e}")
        return False
    
    return True

def main():
    """Main test function."""
    print("Audio Debug Test")
    print("=" * 50)
    print(f"Debug audio saving enabled: {settings.save_debug_audio}")
    print()
    
    # Run the test
    success = test_audio_processing()
    
    if success:
        print("\n✅ Audio debugging test completed successfully!")
        print("\nYou can now play the generated WAV files to verify audio quality:")
        print("  - gemini_original_24000hz.wav: Original 24kHz audio from Gemini")
        print("  - resampled_8000hz.wav: Resampled 8kHz audio")
        print("  - final_mulaw_8000hz.wav: Final MuLaw audio (converted back to PCM)")
    else:
        print("\n❌ Audio debugging test failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())