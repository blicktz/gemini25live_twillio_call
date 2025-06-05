import audioop

def decode_mulaw(payload: bytes, width: int = 2) -> bytes:
    """
    Decodes MuLaw encoded audio data to LPCM (Linear Pulse Code Modulation).

    Args:
        payload: MuLaw encoded audio bytes.
        width: The sample width in bytes for the output LPCM audio.
               Twilio sends 8-bit MuLaw, which expands to 16-bit (2 bytes) LPCM.

    Returns:
        LPCM encoded audio data as bytes.
    """
    # audioop.ulaw2lin expects the MuLaw data and the width of the output LPCM samples.
    # For Twilio's 8-bit MuLaw, this typically converts to 16-bit LPCM, so width should be 2.
    return audioop.ulaw2lin(payload, width)

def encode_mulaw(pcm_data: bytes, width: int = 2) -> bytes:
    """
    Encodes LPCM audio data to MuLaw.

    Args:
        pcm_data: LPCM audio data bytes.
        width: The sample width in bytes of the input LPCM audio (typically 2 for 16-bit PCM).

    Returns:
        MuLaw encoded audio data as bytes.
    """
    # audioop.lin2ulaw expects the LPCM data and the width of the input LPCM samples.
    return audioop.lin2ulaw(pcm_data, width)

def resample_audio(audio_data: bytes, input_rate: int, output_rate: int, width: int = 2, channels: int = 1) -> bytes:
    """
    Resamples audio data from an input rate to an output rate.

    Args:
        audio_data: The audio data to resample (as bytes).
        input_rate: The input sample rate in Hz.
        output_rate: The desired output sample rate in Hz.
        width: The sample width in bytes (e.g., 2 for 16-bit audio).
        channels: The number of audio channels (e.g., 1 for mono).

    Returns:
        The resampled audio data as bytes.
    """
    # audioop.ratecv performs sample rate conversion.
    # It returns a tuple (new_fragment, new_state). We only need new_fragment.
    # `new_state` is for streaming conversions, which we would manage across multiple calls if needed.
    resampled_data, _ = audioop.ratecv(audio_data, width, channels, input_rate, output_rate, None)
    return resampled_data

# Example usage comments:

# Example: Decode Twilio's 8kHz MuLaw to 16-bit LPCM
# Assumes twilio_audio_payload is a byte string of MuLaw data from Twilio.
# pcm_audio = decode_mulaw(twilio_audio_payload, width=2)
# print(f"Decoded {len(twilio_audio_payload)} bytes of MuLaw to {len(pcm_audio)} bytes of LPCM.")

# Example: Resample 8kHz LPCM to 16kHz LPCM for a service like Gemini
# Assumes pcm_audio is 16-bit LPCM at 8kHz.
# pcm_16khz = resample_audio(pcm_audio, input_rate=8000, output_rate=16000, width=2, channels=1)
# print(f"Resampled {len(pcm_audio)} bytes from 8kHz to {len(pcm_16khz)} bytes at 16kHz.")

# Example: Resample 24kHz LPCM (e.g., from Gemini) to 8kHz LPCM for Twilio
# Assumes gemini_audio_output is 16-bit LPCM at 24kHz.
# pcm_8khz_from_gemini = resample_audio(gemini_audio_output, input_rate=24000, output_rate=8000, width=2, channels=1)
# print(f"Resampled {len(gemini_audio_output)} bytes from 24kHz to {len(pcm_8khz_from_gemini)} bytes at 8kHz.")

# Example: Encode 8kHz 16-bit LPCM to MuLaw for Twilio
# Assumes pcm_8khz_output is 16-bit LPCM at 8kHz.
# mulaw_output = encode_mulaw(pcm_8khz_from_gemini, width=2)
# print(f"Encoded {len(pcm_8khz_from_gemini)} bytes of LPCM to {len(mulaw_output)} bytes of MuLaw.")
