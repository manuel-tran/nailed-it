"""
Link-based call helper for ElevenLabs conversational AI.
Generates a phone-friendly URL and polls for the completed transcript.
"""

import time
import urllib.parse

from elevenlabs_tools import (
    init_elevenlabs,
    speech_to_text,
    get_client,
    AGENT_ID,
)

# Base link copied from working script (agent + branch)
BASE_LINK = "https://elevenlabs.io/app/talk-to?agent_id=agent_7501kcc5xtwdejjrz72a4vhdywca&branch_id=agtbrch_8801kcc5xwheew1veqz9gx2jdaxc"


def _build_call_url(order_list: str, target_price: str, site_address: str, vendor_name: str) -> str:
    """Construct the call URL with dynamic variables appended."""
    params = {
        "var_order_list": order_list,
        "var_target_price": target_price,
        "var_site_address": site_address,
        "var_vendor_name": vendor_name,
    }
    query_string = urllib.parse.urlencode(params)
    return f"{BASE_LINK}&{query_string}"


def _list_recent_conversations(client):
    """Return recent conversations (page_size=5) newest-first."""
    resp = client.conversational_ai.conversations.list(agent_id=AGENT_ID, page_size=5)
    return getattr(resp, "conversations", []) or []


def _get_transcript_text(full_details):
    """Normalize transcript to plain text."""
    transcript = getattr(full_details, "transcript", "")
    if isinstance(transcript, str):
        return transcript
    if isinstance(transcript, list):
        parts = []
        for msg in transcript:
            role = str(getattr(msg, "role", "Agent")).capitalize()
            text = getattr(msg, "message", "")
            parts.append(f"{role}: {text}")
        return "\n".join(parts)
    return str(transcript)


def start_voice_conversation(order_list: str, target_price: str, site_address: str, vendor_name: str):
    """
    Generate a call link and poll until the next conversation completes.
    Returns dict with call_url, conversation_id, transcript, success.
    """
    client = get_client()
    if client is None:
        raise Exception("ElevenLabs client not initialized.")

    call_url = _build_call_url(order_list, target_price, site_address, vendor_name)
    print(f"[INFO] Call URL: {call_url}")
    # Capture last known conversation to avoid reprocessing old calls
    # Track conversations seen at start to avoid reprocessing old calls
    initial_convs = _list_recent_conversations(client)
    seen_status = {c.conversation_id: c.status for c in initial_convs}

    # Poll for a new completed conversation
    timeout_secs = 120
    poll_interval = 3
    deadline = time.time() + timeout_secs
    conversation_id = None
    transcript_text = ""
    print(f"[INFO] Call link ready. Waiting up to {timeout_secs}s for a new completed conversation...")

    while time.time() < deadline:
        conversations = _list_recent_conversations(client)
        if not conversations:
            print("[INFO] No calls yet. Still waiting...")
            time.sleep(poll_interval)
            continue

        # Find a conversation that is new (not in seen_status) or updated to completed
        picked = None
        for conv in conversations:
            conv_id = conv.conversation_id
            conv_status = conv.status
            prev_status = seen_status.get(conv_id)
            is_new = prev_status is None

            if is_new:
                print(f"[INFO] New conversation detected: {conv_id} (status={conv_status})")
            elif prev_status != conv_status:
                print(f"[INFO] Conversation {conv_id} status changed: {prev_status} -> {conv_status}")

            # Detect completion before updating the map
            if is_new and conv_status == "completed":
                picked = conv
                seen_status[conv_id] = conv_status
                break
            if (not is_new) and prev_status != "completed" and conv_status == "completed":
                picked = conv
                seen_status[conv_id] = conv_status
                break

            # Update status map for non-completed states
            seen_status[conv_id] = conv_status

        if not picked:
            print("[INFO] No completed conversations yet. Waiting...")
            time.sleep(poll_interval)
            continue

        # We have a completed conversation
        conversation_id = picked.conversation_id
        full_details = client.conversational_ai.conversations.get(conversation_id)
        transcript_text = _get_transcript_text(full_details)
        print(f"Duration: {getattr(full_details, 'duration_secs', 'n/a')}")
        print(f"Transcript: {transcript_text}")
        break

    if not conversation_id:
        print("[WARN] Timed out waiting for a completed conversation.")

    success = bool(conversation_id)
    return {
        "call_url": call_url,
        "conversation_id": conversation_id,
        "transcript": transcript_text,
        "success": success,
    }