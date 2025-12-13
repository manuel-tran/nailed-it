"""
Utility functions for the Claude Streamlit chatbot
"""
import base64
import pandas as pd
import io

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
        "description": "Reads and analyzes CSV data. Default is contracts.csv; set dataset='inventory' to inspect inventory levels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "description": "Which dataset to load: 'contracts' (default) or 'inventory'",
                    "enum": ["contracts", "inventory"]
                }
            },
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
    },
    {
        "name": "send_order_email",
        "description": "Sends an order email to the supplier after user confirmation. Retrieves supplier info from contracts.csv and sends formatted purchase order email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The product ID from contracts (e.g., 'C001')"
                },
                "quantity": {
                    "type": "integer",
                    "description": "The quantity to order"
                }
            },
            "required": ["product_id", "quantity"]
        }
    }
]


def calculate(expression):
    """Safely evaluates a mathematical expression."""
    try:
        if not all(c in "0123456789+-*/(). " for c in expression):
            return "Error: Invalid characters"
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


def read_csv(dataset: str = "contracts"):
    """Reads the contracts or inventory CSV file and returns a formatted summary."""
    try:
        dataset = (dataset or "contracts").strip().lower()
        file_map = {
            "contracts": "contracts.csv",
            "inventory": "inventory.csv",
        }
        if dataset not in file_map:
            return f"Error: Unknown dataset '{dataset}'. Use 'contracts' or 'inventory'."

        file_path = file_map[dataset]
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]

        result = [f"CSV File: {file_path}", ""]
        result.append(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        result.append("")
        result.append(f"Columns: {', '.join(df.columns.tolist())}")
        result.append("")
        result.append("First 10 rows:")
        result.append(df.head(10).to_string())
        result.append("")
        result.append("Data types:")
        result.append(df.dtypes.to_string())

        if dataset == "inventory":
            # Optional storage-based stock assessment if column exists
            storage_col = "storage" if "storage" in df.columns else None
            low_threshold = 5
            high_threshold = 90

            if storage_col:
                df[storage_col] = pd.to_numeric(df[storage_col], errors="coerce")
                low_stock = df[df[storage_col] < low_threshold]
                high_stock = df[df[storage_col] > high_threshold]

                result.append("")
                result.append(f"Low storage (<{low_threshold}%): {len(low_stock)} items")
                if not low_stock.empty:
                    result.append(low_stock[[col for col in df.columns if col in ["product_id", "product_name", "quantity", storage_col]]].to_string(index=False))

                result.append("")
                result.append(f"High storage (>{high_threshold}%): {len(high_stock)} items")
                if not high_stock.empty:
                    result.append(high_stock[[col for col in df.columns if col in ["product_id", "product_name", "quantity", storage_col]]].to_string(index=False))

        return "\n".join(result)
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

def call_local_store(item_name: str, quantity: int) -> str:
    """
    Contact local store via ElevenLabs conversational AI agent for items not available in contracts.
    
    Args:
        item_name: Name of the item to order
        quantity: Quantity of items needed
        
    Returns:
        Confirmation message
    """
    try:
        # Use the wrapper that returns transcript details
        from elevenlabs_call import start_voice_conversation
        
        # Look up contract price for the item to use as target price
        target_price = "Best available price"  # default fallback
        try:
            file_path = "contracts.csv"
            df = pd.read_csv(file_path)
            # Try to find the item by name (case-insensitive partial match)
            matching_rows = df[df['product_name'].str.contains(item_name, case=False, na=False)]
            if not matching_rows.empty:
                unit_price = matching_rows.iloc[0]['unit_price_eur']
                target_price = f"{unit_price:.2f} EUR per unit"
                print(f"[INFO] Found contract price for '{item_name}': {target_price}")
        except Exception as e:
            print(f"[WARN] Could not lookup contract price: {e}")
        
        # Prepare order details for the agent
        order_list = f"{quantity} x {item_name}"
        site_address = "Main Street 12, Munich"  # Could be made dynamic
        vendor_name = "Local Hardware Store"
        
        # Start the voice conversation with the agent
        print(f"🎤 Initiating voice call for {quantity} units of '{item_name}'...")
        
        conversation_info = start_voice_conversation(
            order_list=order_list,
            target_price=target_price,
            site_address=site_address,
            vendor_name=vendor_name
        )
        
        conversation_id = conversation_info.get("conversation_id") if isinstance(conversation_info, dict) else conversation_info
        transcript = conversation_info.get("transcript", "") if isinstance(conversation_info, dict) else ""
        success = conversation_info.get("success", bool(conversation_id)) if isinstance(conversation_info, dict) else bool(conversation_id)

        if success and conversation_id:
            msg = f"📞 Voice call completed for {quantity} units of '{item_name}'. Conversation ID: {conversation_id}"
            # Keep transcript in tool result for Claude to process, but don't display in UI
            if transcript:
                msg += f"\n\nTranscript: {transcript}"
            return msg
        else:
            return f"📞 Voice call initiated for {quantity} units of '{item_name}' but was interrupted."
            
    except Exception as e:
        # Fallback to placeholder if voice call fails
        return f"📞 Local store contact attempted for {quantity} units of '{item_name}'. (Error: {str(e)[:100]})"
    
def get_base64_encoded_image(image_file):
    """Converts an uploaded image file to base64 string."""
    return base64.b64encode(image_file.getvalue()).decode('utf-8')


def save_audio_to_mp3(audio_bytes):
    """Saves audio bytes as MP3 file object."""
    if audio_bytes:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.mp3"
        return audio_file
    return None


def transcribe_audio_with_elevenlabs(audio_bytes):
    """
    Transcribes audio using ElevenLabs' Scribe v1 model.
    
    Args:
        audio_bytes: Raw audio bytes
        
    Returns:
        str: Transcribed text or error message
    """
    try:
        from elevenlabs_tools import speech_to_text
        import tempfile
        import os
        import time
        
        # Save audio bytes to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        try:
            # Retry logic for rate limiting
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Transcribe using ElevenLabs
                    transcription = speech_to_text(temp_file_path)
                    return transcription
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a rate limit error
                    if "429" in error_str or "system_busy" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                            time.sleep(wait_time)
                            continue
                        else:
                            return "Error: ElevenLabs API is busy. Please try again in a moment."
                    else:
                        raise e
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except ImportError:
        return "Error: elevenlabs package not installed. Run: pip install elevenlabs"
    except Exception as e:
        return f"Transcription error: {str(e)[:200]}"  # Truncate long errors


def get_supplier_info(supplier_id):
    """
    Retrieves supplier information from suppliers.csv.
    
    Args:
        supplier_id: The supplier ID (e.g., 'SUP001')
        
    Returns:
        dict: Supplier information or error message
    """
    try:
        df = pd.read_csv("suppliers.csv")
        supplier = df[df['supplier_id'] == supplier_id]
        
        if supplier.empty:
            return {"error": f"Supplier {supplier_id} not found"}
        
        return supplier.iloc[0].to_dict()
    except Exception as e:
        return {"error": f"Error reading supplier data: {e}"}


def send_order_email(to_email, supplier_name, product_name, quantity, unit_price, total_price, delivery_days):
    """
    Sends an order email to the supplier.
    
    Args:
        to_email: Supplier email address
        supplier_name: Name of the supplier
        product_name: Name of the product
        quantity: Quantity to order
        unit_price: Price per unit
        total_price: Total order price
        delivery_days: Expected delivery days
        
    Returns:
        str: Success or error message
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime
        import streamlit as st
        
        # Get email credentials from secrets
        if "SMTP_EMAIL" not in st.secrets or "SMTP_PASSWORD" not in st.secrets:
            return "Error: Email credentials not configured in secrets.toml"
        
        sender_email = st.secrets["SMTP_EMAIL"]
        sender_password = st.secrets["SMTP_PASSWORD"]
        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = st.secrets.get("SMTP_PORT", 587)
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = f"Purchase Order - {product_name}"
        
        # Email body
        body = f"""
Dear {supplier_name},

We would like to place the following order:

Product: {product_name}
Quantity: {quantity}
Unit Price: €{unit_price:.2f}
Total Price: €{total_price:.2f}

Expected Delivery: {delivery_days} working days

Please confirm receipt of this order and provide an estimated delivery date.

Best regards,
Example Build AG
Procurement Department

---
Order Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return f"✅ Order email sent successfully to {to_email} (from {sender_email})"
        
    except Exception as e:
        return f"Error sending email: {str(e)}"


def extract_contract_from_pdf(pdf_file):
    """
    Extracts text from a PDF file.
    
    Args:
        pdf_file: Uploaded file object
        
    Returns:
        str: Extracted text
    """
    try:
        import pypdf
        
        pdf_reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            
        return text
    except Exception as e:
        return f"Error extracting PDF: {e}"


def parse_contract_to_df(text, api_key):
    """
    Parses contract text into a DataFrame matching contracts.csv schema using Claude.
    
    Args:
        text: Raw contract text
        api_key: Anthropic API key
        
    Returns:
        pd.DataFrame: Parsed contract data
    """
    try:
        import anthropic
        import json
        
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""
        Extract the contract data from the text below into a JSON format that matches this CSV schema:
        
        Columns: 
        - contract_id (Extract from date or ID, e.g., ACME_2025)
        - product_id
        - product_name
        - unit
        - quantity (Total contract quantity)
        - unit_price_eur
        - line_total_eur
        - is_c_item (Set to true)
        - used (Set strictly to 0)
        - supplier_id (Generate a generic ID like SUP_NEW if unknown, or extract)
        - payment_terms
        - delivery_days (Extract number of days)
        
        Return ONLY valid JSON list of objects. No other text.
        
        Contract Text:
        {text}
        """
        
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        json_str = response.content[0].text
        
        # Robust JSON extraction: Strip markdown code blocks
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
            
        # Ensure we only try to parse the array
        start_idx = json_str.find('[')
        end_idx = json_str.rfind(']')
        
        if start_idx != -1 and end_idx != -1:
            json_str = json_str[start_idx:end_idx+1]
        
        data = json.loads(json_str)
        
        df = pd.DataFrame(data)
        return df
        
    except Exception as e:
        return f"Error parsing contract: {e}"