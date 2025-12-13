import streamlit as st
import anthropic
import base64

st.title("Claude 4.5 Chatbot (Images & Text)")

# 1. Initialize the Anthropic Client
if "ANTHROPIC_API_KEY" in st.secrets:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
else:
    st.error("Missing ANTHROPIC_API_KEY in .streamlit/secrets.toml")
    st.stop()

# --- TOOL DEFINITION ---
def calculate(expression):
    """Safely evaluates a mathematical expression."""
    try:
        # Limit valid characters for safety
        if not all(c in "0123456789+-*/(). " for c in expression):
            return "Error: Invalid characters"
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

tool_definitions = [{
    "name": "calculate",
    "description": "Evaluates math expressions (e.g., '45 * 12').",
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"]
    }
}]

# 2. Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3. Helper: Convert Uploaded File to Base64
def get_base64_encoded_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# 4. Sidebar for Image Uploads
with st.sidebar:
    st.header("Upload Image")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    
    # Optional: Clear chat button
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.pop("last_uploaded_file", None)
        st.rerun()

# 5. Handle Upload Logic
# We check if a file is present and if we haven't already processed this specific file
if uploaded_file and st.session_state.get("last_uploaded_file") != uploaded_file.name:
    st.session_state["last_uploaded_file"] = uploaded_file.name
    
    # Encode the image
    base64_image = get_base64_encoded_image(uploaded_file)
    media_type = uploaded_file.type
    
    # Add the user message with the image to history
    st.session_state.messages.append({
        "role": "user",
        "content": [
            {
                "type": "image", 
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_image,
                },
            },
            # We add a hidden text block so the model knows context, 
            # or we can wait for the user to type a question below.
            {"type": "text", "text": "I have uploaded this image."} 
        ],
    })
    
    # Force a rerun to show the image immediately in the chat window
    st.rerun()

# 6. Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # The content can be a string (text only) or a list (multimodal)
        if isinstance(message["content"], str):
            st.markdown(message["content"])
        elif isinstance(message["content"], list):
            for block in message["content"]:
                if block["type"] == "text":
                    st.markdown(block["text"])
                elif block["type"] == "image":
                    # We can't easily re-render the base64 string as an image here 
                    # without decoding, so we usually just show a marker or 
                    # the last uploaded image if it's still in the uploader.
                    st.markdown("🖼️ *[Image Uploaded]*")
                    
# 7. User Input & Model Response
# --- MAIN CHAT LOOP WITH TOOLS ---
if prompt := st.chat_input("Ask a question..."):
    # 1. Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Assistant Response Loop
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_text = ""
        
        # Loop required because Claude might use multiple tools in a row
        while True:
            with client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=st.session_state.messages,
                tools=tool_definitions  # <--- PASS TOOLS HERE
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    message_placeholder.markdown(full_text + "▌")
                final_message = stream.get_final_message()

            # Add Claude's response to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_message.content
            })

            # Check if Claude wants to use a tool
            if final_message.stop_reason == "tool_use":
                # Extract tool details
                tool_block = next(b for b in final_message.content if b.type == "tool_use")
                tool_id = tool_block.id
                
                with st.status(f"Using tool: {tool_block.name}", state="running"):
                    # Run the function
                    if tool_block.name == "calculate":
                        result = calculate(tool_block.input["expression"])
                    else:
                        result = "Error: Unknown tool"
                
                # Add tool result to history (so Claude sees it)
                st.session_state.messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result
                    }]
                })
                # The while loop continues, sending the result back to Claude automatically
            else:
                # No more tools needed, we are done
                message_placeholder.markdown(full_text)
                break