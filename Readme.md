# Reels Generator App - BTK Akademi Hackathon

This application generates reels/short-form video content automatically.

## Python Dependencies
1. Create and activate a virtual environment (recommended):
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

2. Install the required Python packages using pip:
```bash
pip install -r requirements.txt
```

## API Keys
Add the following environment variables to your `.env` file:

```
GENAI_API_KEY=your_genai_key
ELEVENLABS_API_KEY=your_eleven_key
OPENAI_API_KEY=your_openai_key
```

Replace `your_genai_key`, `your_eleven_key`, and `your_openai_key` with your actual API keys from the respective services.

## Running the Application
To start the application, run:
```bash
python create_file_in_special.py
```

## Important Notes
- Keep your API keys secure and never commit them to version control
- Make sure to add `.env` to your `.gitignore` file