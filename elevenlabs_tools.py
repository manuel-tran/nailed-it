from elevenlabs.client import ElevenLabs

# Initialize client (you'll pass the API key when calling)
client = None

def init_elevenlabs(api_key: str):
    """Initialize the ElevenLabs client with API key"""
    global client
    client = ElevenLabs(api_key=api_key)

speech_to_text_tool_definition = {
    "name": "speech_to_text",
    "description": "Transcribes speech to text using the ElevenLabs' Scribe v1 model",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
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
    global client
    if client is None:
        raise Exception("ElevenLabs client not initialized. Call init_elevenlabs() first.")
    
    # Open the local file
    with open(file_path, "rb") as audio_file:
        # Call ElevenLabs API with correct parameter name
        result = client.speech_to_text.convert(
            file=audio_file,
            model_id="scribe_v1",
        )
    
    return result.text if hasattr(result, 'text') else str(result)