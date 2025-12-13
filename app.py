import streamlit as st
import anthropic
from utils import (
    calculate,
    read_csv,
    get_base64_encoded_image,
    save_audio_to_mp3,
    transcribe_audio_with_elevenlabs
)

st.title("Claude 4.5 Chatbot (Images, Text & Voice)")

# 1. Initialize the Anthropic Client
if "ANTHROPIC_API_KEY" in st.secrets:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
else:
    st.error("Missing ANTHROPIC_API_KEY in .streamlit/secrets.toml")
    st.stop()

# --- TOOL DEFINITIONS ---
def calculate(expression):
    """Safely evaluates a mathematical expression."""
    try:
        # Limit valid characters for safety
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

def call_local_store(item_name, quantity):
    """Placeholder function to contact local store for items not available in contracts."""
    # TODO: Implement actual local store API call
    return f"📞 Local store contacted for {quantity} units of '{item_name}'. Awaiting confirmation."


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

# 2. Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Hidden System Prompt (not shown to users)
SYSTEM_PROMPT = """
You are an expert Procurement Assistant. Your role is to identify materials, verify contract details, and manage orders using specific tools. You are professional, efficient, and precise.

<workflow_steps>

1. **Input Analysis**
   - If the user provides text: Identify the item name and requested quantity.
   - If the user provides an image: Analyze the image in high detail. Describe visual features, brand markings, or specifications to identify the item.
   - If the quantity is missing, ask the user to specify it before proceeding.

2. **Database Lookup**
   - Use the `read_csv` tool to search for the identified item.
   - Retrieve the: 'Unit Cost', 'Supplier Email', 'Total Contract Limit', and 'Used Amount'.

3. **Availability & Logic Check**
   - STRICTLY check availability first: Calculate (Total Contract Limit - Used Amount).
   - Compare this result against the user's requested quantity.

   **Branch A: Insufficient Funds/Quantity**
   - If the requested amount exceeds the remaining contract limit:
   - Do NOT offer to order via the contract.
   - Immediately use the `call_local_store` tool to arrange the missing items.
   - Inform the user you have contacted the local store.

   **Branch B: Sufficient Funds/Quantity**
   - Use the `calculate` tool to determine the Total Price (Unit Cost * Requested Quantity).
   - Present the item found, the Unit Cost, and the Total Price to the user.
   - Ask for explicit confirmation to proceed.

4. **Execution (Only after User Confirmation)**
   - Once the user confirms the order:
   - A) Write an email to the 'Supplier Email' retrieved from the CSV placing the order. for now use johndoe@test.de as email address.
   - B) Use the `update_used` tool to add the order cost/amount to the 'Used' column in the CSV.
   - C) Confirm to the user that the order has been placed and the contract record updated.

</workflow_steps>

<guidelines>
- Always use the `calculate` tool for math; do not calculate mentally.
- Never place an order or update the CSV without explicit user confirmation.
- If an item is not found in the CSV at all, inform the user and ask for the correct item name or SKU.
</guidelines>
"""

# 3. Helper: Convert Uploaded File to Base64
def get_base64_encoded_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# 4. Sidebar for Image Uploads
with st.sidebar:
    st.header("⚙️ Settings")
    # Developer mode toggle
    dev_mode = st.toggle("Developer Mode", value=False, help="Show tool usage and technical details")
    
    st.divider()
    
    st.header("📷 Upload Image")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    
    st.header("🎤 Voice Memo")
    
    # Add a key to the audio input that we can change to reset it
    if "audio_key" not in st.session_state:
        st.session_state.audio_key = 0
    
    audio_bytes = st.audio_input("Record a voice message", key=f"audio_{st.session_state.audio_key}")
    
    # Auto-transcribe when audio is recorded
    if audio_bytes:
        # Check if this is a new recording
        audio_value = audio_bytes.getvalue()
        
        if "last_audio_hash" not in st.session_state or st.session_state["last_audio_hash"] != hash(audio_value):
            # New recording detected
            st.session_state["last_audio_hash"] = hash(audio_value)
            
            with st.spinner("Transcribing with ElevenLabs..."):
                transcription = transcribe_audio_with_elevenlabs(audio_value)
            
            if transcription.startswith("Error:"):
                st.error(transcription)
            else:
                # Add transcription as user message
                st.session_state.messages.append({
                    "role": "user", 
                    "content": transcription
                })
                # Set flag to trigger Claude response
                st.session_state["trigger_response"] = True
                # Reset audio input for next recording
                st.session_state.audio_key += 1
                st.rerun()
        
        # Show clear button after recording
        if st.button("🔄 Clear Recording (Ready for Next)"):
            st.session_state.audio_key += 1
            st.session_state.pop("last_audio_hash", None)
            st.rerun()
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.pop("last_uploaded_file", None)
        st.session_state.pop("last_audio", None)
        st.rerun()

# 4. Handle Image Upload
if uploaded_file and st.session_state.get("last_uploaded_file") != uploaded_file.name:
    st.session_state["last_uploaded_file"] = uploaded_file.name
    
    base64_image = get_base64_encoded_image(uploaded_file)
    media_type = uploaded_file.type
    
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
            {"type": "text", "text": "I have uploaded this image."} 
        ],
    })
    st.rerun()

# 5. Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], str):
            st.markdown(message["content"])
        elif isinstance(message["content"], list):
            for block in message["content"]:
                block_type = block.get("type") if isinstance(block, dict) else block.type
                
                if block_type == "text":
                    text = block.get("text") if isinstance(block, dict) else block.text
                    st.markdown(text)
                elif block_type == "image":
                    if isinstance(block, dict):
                        import base64
                        image_data = base64.b64decode(block["source"]["data"])
                        st.image(image_data, caption="Uploaded Image")
                    else:
                        st.markdown("🖼️ *[Image]*")
                elif block_type == "tool_use" and dev_mode:
                    # Only show in developer mode
                    name = block.get("name") if isinstance(block, dict) else block.name
                    st.info(f"🔧 Used tool: **{name}**")
                elif block_type == "tool_result" and dev_mode:
                    # Only show in developer mode
                    content = block.get("content") if isinstance(block, dict) else block.content
                    st.success(f"✅ Tool result: {content}")

# 6. User Input & Model Response
# Check if we need to trigger a response (from transcription)
should_respond = st.session_state.pop("trigger_response", False)
display_user_message = False

if prompt := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    should_respond = True
    display_user_message = True

if should_respond:
    # Display the last user message if it's new and from chat input
    if display_user_message:
        with st.chat_message("user"):
            st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_text = ""
        tool_use_count = 0
        max_tool_iterations = 5
        
        while tool_use_count < max_tool_iterations:
            try:
                with client.messages.stream(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1024,
                    messages=st.session_state.messages,
                    tools=tool_definitions,
                    system=SYSTEM_PROMPT
                ) as stream:
                    for text in stream.text_stream:
                        full_text += text
                        message_placeholder.markdown(full_text + "▌")
                    final_message = stream.get_final_message()

                message_placeholder.markdown(full_text)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_message.content
                })

                if final_message.stop_reason == "tool_use":
                    tool_use_count += 1
                    tool_blocks = [b for b in final_message.content if b.type == "tool_use"]
                    
                    for tool_block in tool_blocks:
                        tool_id = tool_block.id
                        tool_name = tool_block.name
                        tool_input = tool_block.input
                        
                        # Only show tool usage in developer mode
                        if dev_mode:
                            st.info(f"🔧 Using tool: **{tool_name}**")
                        
                        result = "Error: Unknown tool"
                        if tool_name == "calculate":
                            result = calculate(tool_input["expression"])
                        elif tool_name == "read_csv":
                            result = read_csv()
                        elif tool_name == "update_used":
                            result = update_used(tool_input["product_id"], tool_input["used_quantity"])
                        elif tool_name == "call_local_store":
                            result = call_local_store(tool_input["item_name"], tool_input["quantity"])
                        
                        # Only show result in developer mode
                        if dev_mode:
                            st.success(f"✅ Result: {result}")
                        
                        st.session_state.messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": str(result)
                            }]
                        })
                    
                    full_text = ""
                else:
                    break
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                break
        
        if tool_use_count >= max_tool_iterations:
            st.warning("⚠️ Maximum tool use iterations reached.")