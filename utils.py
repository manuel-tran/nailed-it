"""
Utility functions for the Claude Streamlit chatbot
"""
import base64
import pandas as pd
import io

tool_definitions = [
    {
        "name": "calculate",
        "description": "Evaluates math expressions (e.g., '45 * 12').",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"]
        }
    },
    {
        "name": "read_csv",
        "description": "Reads and analyzes the contracts database CSV file. Returns column names, shape, first 10 rows, data types, and basic statistics.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_used",
        "description": "Updates the 'used' column for a product in contracts.csv. Validates that the requested quantity doesn't exceed available inventory. Use this when a user orders or consumes items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The product ID (e.g., 'C001', 'C013')"
                },
                "used_quantity": {
                    "type": "integer",
                    "description": "The quantity to add to the 'used' column (positive number)"
                }
            },
            "required": ["product_id", "used_quantity"]
        }
    },
    {
        "name": "call_local_store",
        "description": "Contacts the local store to request items that are not available through existing contracts. Use when contract limits are exceeded or items are not in the contract database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the item to order from the local store"
                },
                "quantity": {
                    "type": "integer",
                    "description": "The quantity needed"
                }
            },
            "required": ["item_name", "quantity"]
        }
    }
]


def calculate(expression):
    """Safely evaluates a mathematical expression."""
    try:
        if not all(c in "0123456789+-*/(). " for c in expression):
            return "Error: Invalid characters"
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


def read_csv():
    """Reads the database CSV file and returns its contents as a formatted string."""
    try:
        # Hardcoded path to the database CSV file
        file_path = "contracts.csv"
        df = pd.read_csv(file_path)
        
        # Return summary of the CSV
        result = f"CSV File: {file_path}\n\n"
        result += f"Shape: {df.shape[0]} rows, {df.shape[1]} columns\n\n"
        result += f"Columns: {', '.join(df.columns.tolist())}\n\n"
        result += f"First 10 rows:\n{df.head(10).to_string()}\n\n"
        result += f"Data types:\n{df.dtypes.to_string()}\n\n"
        result += f"Basic statistics:\n{df.describe().to_string()}"
        return result
    except Exception as e:
        return f"Error reading CSV: {e}"

def update_used(product_id, used_quantity):
    """Updates the 'used' column for a specific product in contracts.csv."""
    try:
        file_path = "contracts.csv"
        df = pd.read_csv(file_path)
        
        # Find the product by product_id
        if product_id not in df['product_id'].values:
            return f"Error: Product ID '{product_id}' not found in database"
        
        # Get the row index
        idx = df[df['product_id'] == product_id].index[0]
        
        # Get current values
        current_used = df.loc[idx, 'used']
        total_quantity = df.loc[idx, 'quantity']
        new_used = current_used + used_quantity
        
        # Check if we're exceeding available quantity
        if new_used > total_quantity:
            available = total_quantity - current_used
            return f"Error: Cannot use {used_quantity} units. Only {available} units available (total: {total_quantity}, already used: {current_used})"
        
        # Update the used column
        df.loc[idx, 'used'] = new_used
        
        # Save back to CSV
        df.to_csv(file_path, index=False)
        
        # Return success message with details
        product_name = df.loc[idx, 'product_name']
        remaining = total_quantity - new_used
        result = f"✅ Updated {product_name} (ID: {product_id})\n"
        result += f"Used: {used_quantity} units\n"
        result += f"Total used: {new_used}/{total_quantity}\n"
        result += f"Remaining: {remaining} units"
        return result
    except Exception as e:
        return f"Error updating CSV: {e}"

def call_local_store(item_name: str, quantity: int) -> str:
    """
    Contact local store via ElevenLabs conversational AI agent for items not available in contracts.
    
    Args:
        item_name: Name of the item to order
        quantity: Quantity of items needed
        
    Returns:
        Confirmation message
    """
    try:
        # Use the wrapper that returns transcript details
        from elevenlabs_call import start_voice_conversation
        
        # Prepare order details for the agent
        order_list = f"{quantity} x {item_name}"
        target_price = "Best available price"
        site_address = "Main Street 12, Munich"  # Could be made dynamic
        vendor_name = "Local Hardware Store"
        
        # Start the voice conversation with the agent
        print(f"🎤 Initiating voice call for {quantity} units of '{item_name}'...")
        
        conversation_info = start_voice_conversation(
            order_list=order_list,
            target_price=target_price,
            site_address=site_address,
            vendor_name=vendor_name
        )
        
        conversation_id = conversation_info.get("conversation_id") if isinstance(conversation_info, dict) else conversation_info
        transcript = conversation_info.get("transcript", "") if isinstance(conversation_info, dict) else ""
        success = conversation_info.get("success", bool(conversation_id)) if isinstance(conversation_info, dict) else bool(conversation_id)

        if success and conversation_id:
            msg = f"📞 Voice call completed for {quantity} units of '{item_name}'. Conversation ID: {conversation_id}"
            if transcript:
                # Include transcript in the returned message so it appears in chat history
                msg += f"\n\n🗒️ Transcript:\n{transcript}"
            return msg
        else:
            return f"📞 Voice call initiated for {quantity} units of '{item_name}' but was interrupted."
            
    except Exception as e:
        # Fallback to placeholder if voice call fails
        return f"📞 Local store contact attempted for {quantity} units of '{item_name}'. (Error: {str(e)[:100]})"
    
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