import streamlit as st
import anthropic
import pandas as pd
from utils import (
    calculate,
    read_csv,
    update_used,
    call_local_store,
    get_base64_encoded_image,
    save_audio_to_mp3,
    transcribe_audio_with_elevenlabs,
    send_order_email,
    get_supplier_info,
    extract_contract_from_pdf,
    parse_contract_to_df
)

from utils import tool_definitions

st.title("🔩 NAIled It – Procurement Assistant for C Materials")
st.caption("C materials are consumable, low-value items like fasteners, nails, screws, and small parts used across projects.")

# 1. Initialize the Anthropic Client
if "ANTHROPIC_API_KEY" in st.secrets:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
else:
    st.error("Missing ANTHROPIC_API_KEY in .streamlit/secrets.toml")
    st.stop()

# Initialize ElevenLabs
if "ELEVENLABS_API_KEY" in st.secrets:
    from elevenlabs_tools import init_elevenlabs
    init_elevenlabs(st.secrets["ELEVENLABS_API_KEY"])
else:
    st.warning("Missing ELEVENLABS_API_KEY - transcription will not work")
    
# 2. Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "message_internal_flags" not in st.session_state:
    st.session_state.message_internal_flags = []
if "precheck_done" not in st.session_state:
    st.session_state.precheck_done = False
if "precheck_in_progress" not in st.session_state:
    st.session_state.precheck_in_progress = False

# Hidden System Prompt (not shown to users)
def order_product(product_id, quantity):
    """
    Wrapper function to handle product ordering via email.
    Retrieves contract and supplier info, then sends order email.
    """
    try:
        # Read contracts to get product and supplier info
        contracts_df = pd.read_csv("contracts.csv")
        product = contracts_df[contracts_df['product_id'] == product_id]
        
        if product.empty:
            return f"Error: Product {product_id} not found in contracts"
        
        product_row = product.iloc[0]
        product_name = product_row['product_name']
        unit_price = product_row['unit_price_eur']
        total_price = unit_price * quantity
        supplier_id = product_row['supplier_id']
        delivery_days = product_row['delivery_days']
        
        # Get supplier info
        supplier_info = get_supplier_info(supplier_id)
        
        if "error" in supplier_info:
            return supplier_info["error"]
        
        supplier_name = supplier_info['supplier_name']
        supplier_email = supplier_info['contact_email']
        
        # Send order email
        result = send_order_email(
            to_email=supplier_email,
            supplier_name=supplier_name,
            product_name=product_name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            delivery_days=delivery_days
        )
        
        return result
        
    except Exception as e:
        return f"Error processing order: {e}"


SYSTEM_PROMPT = """
You are an expert Procurement Assistant. Your role is to identify materials, verify contract details, monitor inventory, and manage orders using specific tools. You are professional, efficient, and precise.

<workflow_steps>

0. **Inventory Pre-Check** (run before answering)
    - Call `read_csv` with dataset="inventory" to inspect current stock and storage percentages.
    - If any item has storage < 5%, ask the user if you should place an order for that item right away.

1. **Input Analysis**
    - If the user provides text: Identify the item name and requested quantity.
    - If the user provides an image: Analyze the image in high detail. Describe visual features, brand markings, or specifications to identify the item.
    - If the quantity is missing, ask the user to specify it before proceeding.

2. **Inventory Check FIRST (Critical Step)**
    - BEFORE doing anything else, call `read_csv` with dataset="inventory" to check current stock levels.
    - Find the requested item and check its storage percentage.
    - **IF storage > 0.9 (90% full):**
        - STOP immediately and inform the user that inventory is at [X]% capacity
        - Warn them that adding this order will cause significant overfill issues
        - Ask: "The inventory for [item] is already at [X]% capacity. Are you absolutely sure you want to proceed with this order?"
        - DO NOT proceed to calculate costs or lookup contracts until user explicitly confirms
        - Wait for user confirmation before continuing
    - **IF storage < 0.9:**
        - Proceed normally to step 3

3. **Database Lookup (Contracts)**
    - Use the `read_csv` tool with dataset="contracts" to search for the identified item.
    - Retrieve: 'Unit Cost', 'Supplier Email', 'Total Contract Limit', and 'Used Amount'.
    - Check contract availability: Calculate (Total Contract Limit - Used Amount) and compare to requested quantity.

    **Branch A: Insufficient Contract Quantity (Partial Contract + Local Store)**
    - If the requested amount exceeds the remaining contract limit:
    - Calculate how much CAN be ordered from the contract: (Total Contract Limit - Used Amount)
    - Calculate the surplus that needs to come from local store: (Requested Quantity - Contract Available)
    - Inform the user of the split order:
        * "The contract only has [X] units remaining, but you want [Y] units."
        * "I'll order [X] from the contract supplier at [contract price]"
        * "And [surplus] from the local store"
    - Ask for explicit confirmation for this split approach
    - After confirmation:
        1. First, process the contract portion (calculate cost, prepare email, update_used)
        2. Then, use `call_local_store` tool for the surplus quantity
        3. Confirm both orders to the user

    **Branch B: Sufficient Contract Quantity**
    - Use the `calculate` tool to determine the Total Price (Unit Cost * Requested Quantity).
    - Present the item found, the Unit Cost, and the Total Price to the user.
    - **IF inventory was high (>90%) and user already confirmed once:**
        - Ask for FINAL confirmation: "Final confirmation: Place order for [quantity] [item] at [price]? This will significantly overfill the inventory."
    - **IF inventory was normal (<90%):**
        - Ask for confirmation to proceed as normal.

4. **Execution (Only after ALL Confirmations)**
    - Once the user confirms the order (and has confirmed twice if inventory was high):
    - A) Write an email to the Supplier Email (already implemented in `order_product` function).
    - B) Use the `update_used` tool to add the order cost/amount to the 'Used' column in the CSV.
    - C) Confirm to the user that the order has been placed and the contract record updated.
    - D) Immediately ask the user if they want to order anything else and be ready to repeat the workflow.

</workflow_steps>

<guidelines>
- Always use the `calculate` tool for math; do not calculate mentally.
- Never place an order or update the CSV without explicit user confirmation.
- For high inventory items (>90%), require TWO confirmations: one when inventory is checked, one before final order placement.
- If an item is not found in the contracts CSV, inform the user and ask for the correct item name or SKU.
- If storage data is missing for an item, continue without storage-based warnings for that item.
- Storage values are decimals (0.99 = 99%, 0.5 = 50%, etc.). Treat anything > 0.9 as critically high.
- If the user requests items that are not typical C materials (e.g., vehicles, heavy machinery, unrelated services), respond that you cannot process non-C-material orders and ask them to provide a C-material item.
</guidelines>
"""

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
                st.session_state.message_internal_flags.append(False)
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
        st.session_state.message_internal_flags = []
        st.session_state.pop("last_uploaded_file", None)
        st.session_state.pop("last_audio", None)
        st.rerun()

    st.divider()
    st.header("📄 Upload Contract PDF")
    uploaded_pdf = st.file_uploader("Choose a PDF contract...", type=["pdf"])
    
    if uploaded_pdf:
        if st.button("extract info"):
            with st.spinner("Parsing contract and updating database..."):
                contract_text = extract_contract_from_pdf(uploaded_pdf)
                
                if contract_text and len(contract_text) > 10:
                    api_key = st.secrets["ANTHROPIC_API_KEY"]
                    df_new = parse_contract_to_df(contract_text, api_key)
                    
                    if isinstance(df_new, pd.DataFrame):
                        if df_new.empty:
                            st.error("⚠️ Parsed data is empty. contracts.csv was NOT updated.")
                        else:
                            # Save to contracts.csv
                            df_new.to_csv("contracts.csv", index=False)
                            st.success("✅ Database updated from Contract PDF!")
                        
                        # Optional: Clear chat to start fresh with new data
                        # st.session_state.messages = []
                    else:
                        st.error(f"Failed to parse data: {df_new}")
                else:
                    st.error("⚠️ Failed to text from PDF.")

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
    st.session_state.message_internal_flags.append(False)
    st.rerun()

# 5. Display Chat History
for message, is_internal in zip(st.session_state.messages, st.session_state.message_internal_flags):
    if is_internal:
        continue
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

# Run one-time inventory pre-check before any user interaction
if not st.session_state.precheck_done:
    st.session_state.precheck_in_progress = True
    st.session_state.messages.append({
        "role": "user",
        "content": "Run startup inventory pre-check (dataset=inventory). List items under 5% storage and ask to place orders for them. Keep it concise."
    })
    st.session_state.message_internal_flags.append(True)
    st.session_state.precheck_done = True
    should_respond = True

if prompt := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.message_internal_flags.append(False)
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
                    temperature=0,
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
                st.session_state.message_internal_flags.append(False)

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
                            dataset = tool_input.get("dataset", "contracts") if tool_input else "contracts"
                            result = read_csv(dataset)
                        elif tool_name == "update_used":
                            result = update_used(tool_input["product_id"], tool_input["used_quantity"])
                        elif tool_name == "call_local_store":
                            result = call_local_store(tool_input["item_name"], tool_input["quantity"])
                            # Only show result in developer mode (no transcript display)
                            if dev_mode:
                                # Show only the first line (summary) without the full transcript
                                summary = result.split("\n\nTranscript:")[0] if "\n\nTranscript:" in result else result
                                st.success(f"✅ Result: {summary}")
                        elif tool_name == "send_order_email":
                            result = order_product(tool_input["product_id"], tool_input["quantity"])
                        else:
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
                        st.session_state.message_internal_flags.append(st.session_state.get("precheck_in_progress", False))
                    
                    full_text = ""
                else:
                    break
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                break
        
        if tool_use_count >= max_tool_iterations:
            st.warning("⚠️ Maximum tool use iterations reached.")

    # Clear precheck flag after response cycle
    if st.session_state.get("precheck_in_progress"):
        st.session_state.precheck_in_progress = False

# 7. Quick Confirm UI (Yes/No)
# Always show confirmation buttons to streamline replies.
c1, c2 = st.columns(2)
with c1:
    if st.button("✅ Yes"):
        st.session_state.messages.append({"role": "user", "content": "Yes, proceed with the action."})
        st.session_state.message_internal_flags.append(False)
        st.session_state["trigger_response"] = True
        st.rerun()
with c2:
    if st.button("❌ No"):
        st.session_state.messages.append({"role": "user", "content": "No, cancel this action."})
        st.session_state.message_internal_flags.append(False)
        st.session_state["trigger_response"] = True
        st.rerun()