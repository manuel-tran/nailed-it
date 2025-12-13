import streamlit as st
import anthropic
import base64
import pandas as pd
import io

st.title("Claude 4.5 Chatbot (Images & Text)")
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
    }
]

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
            {"type": "text", "text": "I have uploaded this image."} 
        ],
    })
    
    st.rerun()

# 6. Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], str):
            st.markdown(message["content"])
        elif isinstance(message["content"], list):
            for block in message["content"]:
                # Handle both dict and object formats
                block_type = block.get("type") if isinstance(block, dict) else block.type
                
                if block_type == "text":
                    text = block.get("text") if isinstance(block, dict) else block.text
                    st.markdown(text)
                elif block_type == "image":
                    # Decode and display the image
                    if isinstance(block, dict):
                        image_data = base64.b64decode(block["source"]["data"])
                        st.image(image_data, caption="Uploaded Image")
                    else:
                        st.markdown("🖼️ *[Image]*")
                elif block_type == "tool_use":
                    name = block.get("name") if isinstance(block, dict) else block.name
                    st.info(f"🔧 Used tool: **{name}**")
                elif block_type == "tool_result":
                    content = block.get("content") if isinstance(block, dict) else block.content
                    st.success(f"✅ Tool result: {content}")

# 7. User Input & Model Response
if prompt := st.chat_input("Ask a question..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant Response Loop with tool handling
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_text = ""
        tool_use_count = 0
        max_tool_iterations = 5  # Prevent infinite loops
        
        while tool_use_count < max_tool_iterations:
            try:
                # 1. Call the API
                with client.messages.stream(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1024,
                    messages=st.session_state.messages,
                    tools=tool_definitions,
                    system="You are a helpful assistant with access to a calculator, a contracts database CSV reader, and an inventory update tool. Help users track and manage their contract inventory."
                ) as stream:
                    for text in stream.text_stream:
                        full_text += text
                        message_placeholder.markdown(full_text + "▌")
                    final_message = stream.get_final_message()

                # 2. Finalize text display for this turn
                message_placeholder.markdown(full_text)

                # 3. Add Claude's response to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_message.content
                })

                # 4. Check if Claude wants to use a tool
                if final_message.stop_reason == "tool_use":
                    tool_use_count += 1
                    
                    # Extract tool details
                    tool_blocks = [b for b in final_message.content if b.type == "tool_use"]
                    
                    for tool_block in tool_blocks:
                        tool_id = tool_block.id
                        tool_name = tool_block.name
                        tool_input = tool_block.input
                        
                        # Show tool usage to user
                        st.info(f"🔧 Using tool: **{tool_name}**")
                        
                        # Run the function
                        result = "Error: Unknown tool"
                        if tool_name == "calculate":
                            result = calculate(tool_input["expression"])
                        elif tool_name == "read_csv":
                            result = read_csv()
                        elif tool_name == "update_used":
                            result = update_used(tool_input["product_id"], tool_input["used_quantity"])
                        
                        st.success(f"✅ Result: {result}")
                        
                        # Add tool result to history
                        st.session_state.messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": str(result)
                            }]
                        })
                    
                    # Clear the text for next iteration (Claude's interpretation of the result)
                    full_text = ""
                    # The loop continues here to send the result back to Claude
                else:
                    # No tool used, we are done
                    break
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                break
        
        if tool_use_count >= max_tool_iterations:
            st.warning("⚠️ Maximum tool use iterations reached.")