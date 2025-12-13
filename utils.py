"""
Utility functions for the Claude Streamlit chatbot
"""
import base64
import pandas as pd
import io


def calculate(expression):
    """Safely evaluates a mathematical expression."""
    try:
        if not all(c in "0123456789+-*/(). " for c in expression):
            return "Error: Invalid characters"
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


def read_csv(file_path="database.csv"):
    """Reads the database CSV file and returns its contents as a formatted string."""
    try:
        df = pd.read_csv(file_path)
        
        result = f"CSV File: {file_path}\n\n"
        result += f"Shape: {df.shape[0]} rows, {df.shape[1]} columns\n\n"
        result += f"Columns: {', '.join(df.columns.tolist())}\n\n"
        result += f"First 10 rows:\n{df.head(10).to_string()}\n\n"
        result += f"Data types:\n{df.dtypes.to_string()}\n\n"
        result += f"Basic statistics:\n{df.describe().to_string()}"
        return result
    except Exception as e:
        return f"Error reading CSV: {e}"


def get_base64_encoded_image(image_file):
    """Converts an uploaded image file to base64 string."""
    return base64.b64encode(image_file.getvalue()).decode('utf-8')


def save_audio_to_mp3(audio_bytes):
    """Saves audio bytes as MP3 file object."""
    if audio_bytes:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.mp3"
        return audio_file
    return None


def transcribe_audio_with_elevenlabs(audio_bytes):
    """
    Transcribes audio using ElevenLabs' Scribe v1 model.
    
    Args:
        audio_bytes: Raw audio bytes
        
    Returns:
        str: Transcribed text or error message
    """
    try:
        from elevenlabs_tools import speech_to_text
        import tempfile
        import os
        import time
        
        # Save audio bytes to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        try:
            # Retry logic for rate limiting
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Transcribe using ElevenLabs
                    transcription = speech_to_text(temp_file_path)
                    return transcription
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a rate limit error
                    if "429" in error_str or "system_busy" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                            time.sleep(wait_time)
                            continue
                        else:
                            return "Error: ElevenLabs API is busy. Please try again in a moment."
                    else:
                        raise e
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except ImportError:
        return "Error: elevenlabs package not installed. Run: pip install elevenlabs"
    except Exception as e:
        return f"Transcription error: {str(e)[:200]}"  # Truncate long errors