from elevenlabs.client import ElevenLabs

# Initialize client (you'll pass the API key when calling)
client = None
AGENT_ID = "agent_7501kcc5xtwdejjrz72a4vhdywca"

def init_elevenlabs(api_key: str):
    """Initialize the ElevenLabs client with API key"""
    global client
    client = ElevenLabs(api_key=api_key)

def get_client():
    """Accessor for the initialized ElevenLabs client."""
    global client
    return client

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
        conversation_id after session ends
    """
    global client
    if client is None:
        raise Exception("ElevenLabs client not initialized.")
    
    try:
        from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
        from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
        
        print("--- Starting Conversation ---")
        print(f"Order: {order_list}")
        print(f"Target Price: {target_price}")
        print(f"Address: {site_address}")
        print(f"Vendor: {vendor_name}")
        print("Speak into your microphone. Press Ctrl+C to stop.")
        
        print("\n[DEBUG] Creating Conversation object...")
        # Build initiation config with dynamic variables per ElevenLabs SDK docs
        config = ConversationInitiationData(
            dynamic_variables={
                "order_list": order_list,
                "target_price": target_price,
                "site_address": site_address,
                "vendor_name": vendor_name,
            }
        )
        
        # Track activity and auto-end on keywords/silence
        import time
        last_activity = {"time": time.time()}
        conversation_ref = {"obj": None}
        
        def on_agent_response(response):
            print(f"Agent: {response}")
            last_activity["time"] = time.time()
            # Auto-end on 'goodbye' or 'auf wiederhören'
            response_lower = response.lower()
            if "goodbye" in response_lower or "auf wiederhören" in response_lower:
                try:
                    print(f"[INFO] End phrase detected: '{response[:50]}...'. Ending session...")
                    if conversation_ref["obj"]:
                        conversation_ref["obj"].end_session()
                except Exception as e:
                    print(f"[WARN] Failed to end session on end phrase: {e}")
        
        def on_user_transcript(transcript):
            print(f"You: {transcript}")
            last_activity["time"] = time.time()
            # User says goodbye or auf wiederhören
            transcript_lower = transcript.lower()
            if "goodbye" in transcript_lower or "auf wiederhören" in transcript_lower:
                try:
                    print(f"[INFO] User said goodbye/auf wiederhören. Ending session...")
                    if conversation_ref["obj"]:
                        conversation_ref["obj"].end_session()
                except Exception as e:
                    print(f"[WARN] Failed to end session on user end phrase: {e}")
        
        # Initialize conversation using config
        conversation = Conversation(
            client,
            AGENT_ID,
            config=config,
            requires_auth=True,
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=on_agent_response,
            callback_user_transcript=on_user_transcript,
        )
        conversation_ref["obj"] = conversation
        print("[DEBUG] Conversation object created successfully")
        
        # Start the session
        print("[DEBUG] Starting session...")
        conversation.start_session()
        print("[DEBUG] Session started, monitoring for activity...")
        
        try:
            import time
            import threading
            silence_timeout = 60  # seconds
            session_ended = {"value": False}
            conversation_id = None
            
            # Background thread to monitor silence
            def silence_monitor():
                while not session_ended["value"]:
                    time.sleep(2)
                    elapsed = time.time() - last_activity["time"]
                    if elapsed > silence_timeout and not session_ended["value"]:
                        try:
                            print(f"[INFO] {silence_timeout}s silence detected. Ending session...")
                            conversation.end_session()
                            session_ended["value"] = True
                        except Exception as e:
                            print(f"[WARN] Silence monitor end_session failed: {e}")
                        break
            
            monitor_thread = threading.Thread(target=silence_monitor, daemon=True)
            monitor_thread.start()
            
            # Wait for session end (either natural or triggered by callbacks/monitor)
            conversation_id = conversation.wait_for_session_end()
            session_ended["value"] = True
            
            # Fallback if attribute exists on object instead
            if not conversation_id and hasattr(conversation, "conversation_id"):
                conversation_id = conversation.conversation_id
            print(f"[DEBUG] Conversation ended. ID: {conversation_id}")

            # Fetch the full conversation object from the API for details
            try:
                full_conversation = client.conversational_ai.conversations.get(conversation_id)
                print(f"Duration: {getattr(full_conversation, 'duration_secs', 'n/a')}")
                print(f"Transcript: {getattr(full_conversation, 'transcript', '')}")
            except Exception as e:
                print(f"[WARN] Failed to fetch full conversation details: {e}")

            return conversation_id
        except KeyboardInterrupt:
            print("[DEBUG] KeyboardInterrupt detected")
            conversation.end_session()
            print("\nConversation stopped by user.")
            return None
            
    except Exception as e:
        # Get full error details
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