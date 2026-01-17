import os
import httpx
from groq import AsyncGroq

# Idealmente, esto viene de settings.py o variables de entorno
from translator.constants import GROQ_API_KEY

class TranslationService:
    """Translation Service."""

    LANG_NAMES = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "pt": "Portuguese",
        "ja": "Japanese",
    }

    def __init__(self):
        self.http_client = httpx.AsyncClient()
        
        self.client = AsyncGroq(
            api_key=GROQ_API_KEY,
            http_client=self.http_client, # <--- 3. INYECTAMOS EL CLIENTE
        )

    async def translate(self, text, source_lang="es", target_lang="en"):
        # Convertimos "fr" -> "French" para que el LLM entienda mejor
        target_name = self.LANG_NAMES.get(target_lang, "English")

        system_prompt = (
            f"You are a professional simultaneous interpreter. "
            f"Translate the following text to {target_name}. " # <--- DINÁMICO
            "Do not explain. Output ONLY the translation. "
            "Keep the tone conversational but professional."
        )

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=1024,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq Error: {e}")
            return text # Fallback: devolver original si falla
    
    async def close(self):
        await self.http_client.aclose()