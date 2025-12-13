import elevenlabs

speech_to_text_tool_definition = {
    "name": "speech_to_text",
    "description": "Transcribes speech to text using the ElevenLabs' Scribe v1 model",
    "input_schema":
        {
            "type": "object",
            "properties":
                {
                    "file_path":
                        {
                            "type": "string",
                            "description": "The local file path to the MP3 audio file."
                        }
                },
            "required": ["file_path"]
        }
}


def speech_to_text(file_path: str) -> str:
    """
    Transcribe speech to text with the world's most accurate ASR model.
    """
    # Open the local file
    with open(file_path, "rb") as audio_data:
        # Call ElevenLabs API
        transcription = elevenlabs.speech_to_text.convert(
            file=audio_data,
            model_id="scribe_v1",
            tag_audio_events=True,
            language_code="eng",
            diarize=True,
        )
    return transcription.text
