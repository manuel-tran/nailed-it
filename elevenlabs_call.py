from elevenlabs.client import ElevenLabs

# Initialize client (you'll pass the API key when calling)
client = None

# IMPORTANT: Replace this with your actual agent ID from ElevenLabs dashboard
AGENT_ID = "agent_7501kcc5xtwdejjrz72a4vhdywca"  # ← UPDATE THIS WITH YOUR CORRECT AGENT ID

def init_elevenlabs(api_key: str):
    """Initialize the ElevenLabs client with API key"""
    global client
    client = ElevenLabs(api_key=api_key)
    print(f"[INFO] ElevenLabs initialized with agent ID: {AGENT_ID}")

# Tool definition for Claude
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

# Tool definition for calling local store
call_local_store_tool_definition = {
    "name": "call_local_store",
    "description": "Contact local store for items not available in contracts. Use this when an item cannot be found in the database or contracts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "item_name": {
                "type": "string",
                "description": "Name of the item to order"
            },
            "quantity": {
                "type": "integer",
                "description": "Quantity of items needed"
            }
        },
        "required": ["item_name", "quantity"]
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

def call_local_store(item_name: str, quantity: int) -> str:
    """
    Placeholder function to contact local store for items not available in contracts.
    
    Args:
        item_name: Name of the item to order
        quantity: Quantity of items needed
        
    Returns:
        Confirmation message
    """
    # TODO: Implement actual local store API call
    return f"📞 Local store contacted for {quantity} units of '{item_name}'. Awaiting confirmation."

def start_voice_conversation(order_list: str, target_price: str, site_address: str, vendor_name: str):
    """
    Start an ElevenLabs conversational AI session.
    
    Args:
        order_list: List of items to order
        target_price: Target price for items
        site_address: Delivery address
        vendor_name: Vendor name
        
    Returns:
        dict with conversation_id and transcript
    """
    global client
    if client is None:
        raise Exception("ElevenLabs client not initialized.")
    
    try:
        from elevenlabs.conversational_ai.conversation import Conversation
        from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
        import threading
        import time
        
        print("--- Starting Conversation ---")
        print(f"Order: {order_list}")
        print(f"Target Price: {target_price}")
        print(f"Address: {site_address}")
        print(f"Vendor: {vendor_name}")
        print("Speak into your microphone. The call will auto-end after 30 seconds of silence or when the agent confirms.")
        
        # Capture conversation transcript
        transcript = []
        call_active = {"active": True, "last_activity": time.time()}
        
        def on_agent_response(response):
            print(f"Agent: {response}")
            transcript.append(f"Agent: {response}")
            call_active["last_activity"] = time.time()
            
            # Check if agent confirmed the order (customize these keywords)
            confirmation_keywords = ["confirmed", "order placed", "all set", "got it", "received", "I confirm teh order"]
            if any(keyword in response.lower() for keyword in confirmation_keywords):
                print("[INFO] Order confirmation detected, ending call...")
                call_active["active"] = False
        
        def on_user_transcript(user_text):
            print(f"You: {user_text}")
            transcript.append(f"User: {user_text}")
            call_active["last_activity"] = time.time()
        
        print("\n[DEBUG] Creating Conversation object...")
        conversation = Conversation(
            client=client,
            agent_id=AGENT_ID,
            requires_auth=True,
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=on_agent_response,
            callback_user_transcript=on_user_transcript,
            dynamic_variables={
                "order_list": order_list,
                "target_price": target_price,
                "site_address": site_address,
                "vendor_name": vendor_name,
            },
        )
        print("[DEBUG] Conversation object created successfully")
        
        print("[DEBUG] Starting session...")
        conversation.start_session()
        print("[DEBUG] Session started, call is active...")
        
        # Auto-end call after timeout or confirmation
        def monitor_call():
            timeout = 30  # seconds of silence before auto-ending
            while call_active["active"]:
                time.sleep(1)
                elapsed = time.time() - call_active["last_activity"]
                if elapsed > timeout:
                    print(f"[INFO] {timeout}s of silence detected, ending call...")
                    call_active["active"] = False
                    break
        
        # Start monitoring in background
        monitor_thread = threading.Thread(target=monitor_call, daemon=True)
        monitor_thread.start()
        
        try:
            # Wait for call to end (either by monitor or natural end)
            while call_active["active"]:
                time.sleep(0.5)
            
            # End the session
            print("[DEBUG] Ending session...")
            conversation.end_session()
            
            # Get conversation ID if available
            conversation_id = getattr(conversation, 'conversation_id', 'unknown')
            
            print(f"[DEBUG] Conversation ended. ID: {conversation_id}")
            
            # Return both ID and transcript
            return {
                "conversation_id": conversation_id,
                "transcript": "\n".join(transcript),
                "success": True
            }
            
        except KeyboardInterrupt:
            print("[DEBUG] KeyboardInterrupt detected")
            conversation.end_session()
            print("\nConversation stopped by user.")
            return {
                "conversation_id": "interrupted",
                "transcript": "\n".join(transcript),
                "success": False
            }
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("\n" + "="*60)
        print("❌ VOICE CONVERSATION ERROR:")
        print("="*60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nFull traceback:")
        print(error_details)
        print("="*60 + "\n")
        raise Exception(f"Conversation failed: {str(e)}")