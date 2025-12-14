import json
import streamlit as st
import time
import urllib.parse
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=st.secrets["ELEVENLABS_API_KEY"])
AGENT_ID = "agent_7501kcc5xtwdejjrz72a4vhdywca"

from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

dynamic_vars = {
    "order_list": "6 x screws",
    "target_price": "1$ per screw",
    "site_address": "Main Street 12, Munich",
    "vendor_name": "Bauhaus Professional",
}

config = ConversationInitiationData(  #
    dynamic_variables=dynamic_vars
)

# Your Variables
dynamic_vars = {
    "order_list": "6 x rubber ducks",
    "target_price": "1$ per screw",
    "site_address": "Main Street 12, Munich",
    "vendor_name": "Bauhaus Professional",
}

# Paste the EXACT link you found on the website here:
BASE_LINK = "https://elevenlabs.io/app/talk-to?agent_id=agent_7501kcc5xtwdejjrz72a4vhdywca&branch_id=agtbrch_8801kcc5xwheew1veqz9gx2jdaxc"


def main():
    print("--- 📡 LIVE CALL MONITOR ---")
    print("Waiting for a call to start on your phone...")

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

        print("🎉 DEMO COMPLETE")


if __name__ == "__main__":
    main()
