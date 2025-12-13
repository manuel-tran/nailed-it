"""
Lightweight wrappers delegating to elevenlabs_tools to avoid duplication.
Provides a richer start_voice_conversation that returns transcript details.
"""

from elevenlabs_tools import (
    init_elevenlabs,
    speech_to_text,
    start_voice_conversation as start_voice_conversation_core,
    get_client,
)

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
    client = get_client()
    if client is None:
        raise Exception("ElevenLabs client not initialized.")

    # Delegate conversation to core implementation
    conversation_id = start_voice_conversation_core(
        order_list=order_list,
        target_price=target_price,
        site_address=site_address,
        vendor_name=vendor_name,
    )

    # Attempt to fetch conversation details (duration + transcript)
    transcript_text = ""
    try:
        full_conversation = client.conversational_ai.conversations.get(conversation_id)
        print(f"Duration: {getattr(full_conversation, 'duration_secs', 'n/a')}")
        print(f"Transcript: {getattr(full_conversation, 'transcript', '')}")
        transcript_text = getattr(full_conversation, 'transcript', '')
    except Exception as e:
        print(f"[WARN] Failed to fetch full conversation details: {e}")

    return {
        "conversation_id": conversation_id,
        "transcript": transcript_text,
        "success": bool(conversation_id)
    }