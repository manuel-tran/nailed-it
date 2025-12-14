from elevenlabs.client import ElevenLabs
import urllib.parse

# Initialize client (you'll pass the API key when calling)
client = None
AGENT_ID = "agent_7501kcc5xtwdejjrz72a4vhdywca"
BASE_LINK = "https://elevenlabs.io/app/talk-to?agent_id=agent_7501kcc5xtwdejjrz72a4vhdywca&branch_id=agtbrch_8801kcc5xwheew1veqz9gx2jdaxc"


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

# Tool definition for calling local store
call_local_store_tool_definition = {
    "name":
        "call_local_store",
    "description":
        "Contact local store for items not available in contracts. Use this when an item cannot be found in the database or contracts.",
    "input_schema":
        {
            "type": "object",
            "properties":
                {
                    "item_name":
                        {
                            "type": "string",
                            "description": "Name of the item to order"
                        },
                    "quantity":
                        {
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
        raise Exception(
            "ElevenLabs client not initialized. Call init_elevenlabs() first."
        )

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


def start_voice_conversation(
    order_list: str, target_price: str, site_address: str, vendor_name: str
):
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
        dynamic_vars = {
            "order_list": order_list,
            "target_price": target_price,
            "site_address": site_address,
            "vendor_name": vendor_name,
        }

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
                    print(
                        f"[INFO] End phrase detected: '{response[:50]}...'. Waiting 10s before ending session..."
                    )
                    time.sleep(
                        10
                    )  # Let the agent finish any buffered speech before closing
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
                    print(
                        f"[INFO] User said goodbye/auf wiederhören. Ending session..."
                    )
                    if conversation_ref["obj"]:
                        conversation_ref["obj"].end_session()
                except Exception as e:
                    print(f"[WARN] Failed to end session on user end phrase: {e}")

        params = {f"var_{k}": v for k, v in dynamic_vars.items()}
        query_string = urllib.parse.urlencode(params)
        final_url = f"{BASE_LINK}&{query_string}"
        try:
            # Send the link via email for demo purposes
            from utils import send_demo_call_link
            send_demo_call_link("maxhoermann99@gmail.com", final_url)
        except Exception as e:
            # Fallback to printing if email fails
            print(f"[WARN] Failed to send demo call link via email: {e}")
            print(final_url)

        # 1. Find the Active Call
        active_call_id = None
        while not active_call_id:
            try:
                # We look for the most recent conversation
                # Note: Use .list() or .get_conversations() depending on SDK version
                resp = client.conversational_ai.conversations.list(
                    agent_id=AGENT_ID, page_size=1
                )
                history = resp.conversations if hasattr(resp, 'conversations') else resp
                if history:
                    latest = history[0]
                    # If we find a call that is currently 'processing' (Active)
                    if latest.status == "processing":
                        active_call_id = latest.conversation_id
                        print(f"\n🚀 Call Detected! (ID: {active_call_id})")
                        print("Streaming transcript...\n")
                        break
                time.sleep(1)  # Check every second
                print(".", end="", flush=True)
            except Exception as e:
                time.sleep(1)

        # 2. Live Loop - Print new messages as they arrive
        processed_message_count = 0
        while True:
            try:
                # Fetch the FULL details of the active call
                details = client.conversational_ai.conversations.get(active_call_id)
                # Check if there are NEW messages we haven't printed yet
                current_transcript = details.transcript
                if len(current_transcript) > processed_message_count:
                    # Only get the new ones
                    new_messages = current_transcript[processed_message_count:]
                    for msg in new_messages:
                        # Print it nicely
                        role = str(msg.role).capitalize()
                        print(f"[{role}]: {msg.message}")
                        # --- YOUR HACKATHON LOGIC HERE ---
                        if role == "User" and "screws" in msg.message:
                            print("   >>> ✅ DETECTED ORDER ITEM: SCREWS")
                        # ---------------------------------
                    # Update our counter
                    processed_message_count = len(current_transcript)
                # Check if call has ended
                if details.status == "done" or details.status == "success":
                    print("\n📞 Call Finished.")
                    break
                elif details.status == "failed":
                    print("\n❌ Call Failed.")
                    break
                time.sleep(1)  # Poll every 1 second for updates
            except KeyboardInterrupt:
                break
            except Exception as e:
                # Sometimes the API might timeout, just ignore and try again
                time.sleep(1)

        return True, current_transcript

    except Exception as e:
        # Get full error details
        import traceback
        error_details = traceback.format_exc()
        print("\n" + "=" * 60)
        print("❌ VOICE CONVERSATION ERROR:")
        print("=" * 60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nFull traceback:")
        print(error_details)
        print("=" * 60 + "\n")
        raise Exception(f"Conversation failed: {str(e)}")
