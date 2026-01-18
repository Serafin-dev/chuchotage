import os

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional simultaneous interpreter. "
    "Translate the following text to {target_name}. "
    "Do not explain. Output ONLY the translation. "
    "Keep the tone conversational but professional."
)
