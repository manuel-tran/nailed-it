from elevenlabs.client import ElevenLabs
import streamlit as st

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


def main():
    print("--- Starting Conversation ---")
    print("Speak into your microphone. Press Ctrl+C to stop.")

    # 2. Initialize the conversation
    conversation = Conversation(
        client=client,
        agent_id=AGENT_ID,
        user_id=None,
        config=config,
        requires_auth=True,
        audio_interface=DefaultAudioInterface(),
        callback_agent_response=lambda response: print(f"Agent: {response}"),
        callback_user_transcript=lambda transcript: print(f"You: {transcript}"),
    )

    # 3. Start the loop
    conversation.start_session()

    # Keep the script running to maintain the connection
    try:
        conversation_id = conversation.wait_for_session_end()
        print(f"Conversation ended. ID: {conversation_id}")
    except KeyboardInterrupt:
        conversation.end_session()
        print("\nConversation stopped by user.")

    # Fetch the full conversation object from the API
    full_conversation = client.conversational_ai.conversations.get(conversation_id)
    print(f"Duration: {full_conversation.duration_secs}")
    print(f"Transcript: {full_conversation.transcript}")


if __name__ == "__main__":
    main()
