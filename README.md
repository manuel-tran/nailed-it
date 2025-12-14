# 🔩 NAIled It – Procurement Assistant for C Materials

A Streamlit-based procurement assistant that helps with ordering consumable materials (C materials like fasteners, nails, screws, and small parts) using Claude AI and voice interactions via ElevenLabs.

## Features

- **Automated Inventory Checks**: Checks your inventory and proposes orders based on this.
- **AI-Powered Procurement**: Uses Claude AI for intelligent order processing
- **Voice Conversations**: ElevenLabs integration for automated local store voice call ordering
- **Speech Transcription**: Automated speech-to-text
- **Database Management**: CSV-based inventory and supplier management
- **Contract Integration**: PDF contract extraction and parsing
- **Email Notifications**: Order confirmations sent via email to contractor

## Coming Soon
- **Sponsor integration**: Call local construction stores based on sponsoring
- **Integration with Twilio**: Actual Phone calls
- **Order Reccomendation**: Based on purchase history or construction plan, or commonly bought together items
- **Mobile App**


## Prerequisites

- **macOS** (required for some dependencies)
- **Python 3.8+**
- **Homebrew** (for system dependencies)

## Setup Instructions

### 1. Install System Dependencies

Before installing Python packages, you need to install PortAudio (required for PyAudio):

```bash
brew install portaudio
```

### 2. Create Virtual Environment (Optional but Recommended)

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies include:
- `streamlit` - Web framework
- `anthropic` - Claude AI API
- `elevenlabs` - Voice AI integration
- `pyaudio` - Audio processing
- `pandas` - Data handling
- `pypdf` - PDF processing

### 4. Configure API Keys

Create a Streamlit secrets file to store your API keys:

```bash
mkdir -p .streamlit
touch .streamlit/secrets.toml
```

Add the following to `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "your-anthropic-api-key-here"
ELEVENLABS_API_KEY = "your-elevenlabs-api-key-here"
SMTP_EMAIL = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-password"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
```

### 5. Set Agent ID (Optional)

If using a custom ElevenLabs agent, update the `AGENT_ID` in `elevenlabs_tools.py`:

```python
AGENT_ID = "your-agent-id-here"
```

## Running the Application

### Start the Streamlit App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Voice Conversation Features

- Speak into your microphone for voice-based ordering
- Press `Ctrl+C` to stop the conversation
- The assistant will auto-end after 60 seconds of silence or on farewell phrases

## Data Files

The application uses CSV files for data management:

- **database.csv** - Inventory of available items
- **contracts.csv** - Contract details and terms
- **inventory.csv** - Current inventory levels

## Troubleshooting

### PyAudio Installation Issues

If you get errors installing PyAudio:

```bash
brew install portaudio
pip install pyaudio
```

### API Key Issues

- Ensure `.streamlit/secrets.toml` exists and has correct formatting
- API keys should not have spaces or extra quotes
- Check that `.streamlit/secrets.toml` is in `.gitignore` (not committed to git)

### Streamlit Secrets Not Found

Make sure the secrets file is in the `.streamlit/` directory:

```bash
ls -la .streamlit/secrets.toml
```

### Audio/Microphone Issues

- Ensure your system microphone is enabled and working
- Check system audio permissions for the terminal/IDE
- Try testing with `python -c "import pyaudio; print(pyaudio.PyAudio().get_device_count())"`

## Project Structure

```
.
├── app.py                    # Main Streamlit application
├── elevenlabs_tools.py       # ElevenLabs integration and tools
├── elevenlabs_call.py        # Voice conversation handling
├── utils.py                  # Utility functions
├── suppliers.csv             # Supplier data
├── contracts.csv             # Contract information
└── .streamlit/
    └── secrets.toml          # API keys (not in git)
```

## Security Notes

- **Never commit** `.streamlit/secrets.toml` to version control
- Ensure `.gitignore` includes `.streamlit/secrets.toml`
- Rotate API keys regularly
- Use app-specific passwords for email (Gmail App Passwords)

## Support

For issues with specific integrations:
- **Claude AI**: See [Anthropic API docs](https://docs.anthropic.com)
- **ElevenLabs**: See [ElevenLabs docs](https://docs.elevenlabs.io)
- **Streamlit**: See [Streamlit docs](https://docs.streamlit.io)
