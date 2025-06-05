from pydantic import BaseModel, Field
import json

class TwilioStreamStop(BaseModel):
    """
    Represents a 'stop' message to be sent to Twilio to terminate a media stream.
    The structure is based on Twilio's expected JSON format for stopping a stream.
    """
    event: str = "stop"
    stop: dict = Field(default_factory=lambda: {"streamSid": None})

    def set_stream_sid(self, stream_sid: str):
        """
        Sets the streamSid for the stop message.

        Args:
            stream_sid: The unique identifier of the stream to be stopped.
        """
        self.stop["streamSid"] = stream_sid

    def to_json(self) -> str:
        """
        Serializes the model to a JSON string.
        Pydantic's model_dump_json is used for correct serialization.
        """
        return self.model_dump_json()

class TwilioMediaMessage(BaseModel):
    """
    Represents a 'media' message for sending audio data to Twilio's media stream.
    The structure is based on Twilio's expected JSON format for media messages.
    """
    event: str = "media"
    stream_sid: str = Field(..., description="The unique identifier for the media stream.")
    media: dict = Field(default_factory=dict, description="Contains the audio payload.")

    def set_payload(self, audio_payload_b64: str):
        """
        Sets the base64 encoded audio payload for the media message.

        Args:
            audio_payload_b64: A base64 encoded string of the audio chunk.
        """
        self.media["payload"] = audio_payload_b64

    def to_json(self) -> str:
        """
        Serializes the model to a JSON string.
        Pydantic's model_dump_json is used for correct serialization.
        """
        # Pydantic's model_dump_json is preferred for correct serialization
        return self.model_dump_json()

# Example usage (for documentation purposes, not to be run directly in models.py)
# if __name__ == "__main__":
#     # Example for sending media
#     media_message = TwilioMediaMessage(stream_sid="MZxxxxxxxxxxxxxxx", event="media")
#     media_message.set_payload("YOUR_BASE64_ENCODED_AUDIO_CHUNK")
#     print(media_message.to_json()) # Output: {"event":"media","stream_sid":"MZxxxxxxxxxxxxxxx","media":{"payload":"YOUR_BASE64_ENCODED_AUDIO_CHUNK"}}

#     # Example for stopping the stream
#     stop_message = TwilioStreamStop(event="stop") # streamSid can be set later or at initialization if known
#     stop_message.set_stream_sid("MZxxxxxxxxxxxxxxx")
#     print(stop_message.to_json()) # Output: {"event":"stop","stop":{"streamSid":"MZxxxxxxxxxxxxxxx"}}
