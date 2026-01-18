import os
import httpx
from groq import AsyncGroq

# Idealmente, esto viene de settings.py o variables de entorno
from translator.constants import GROQ_API_KEY, TRANSLATION_SYSTEM_PROMPT


class TranslationService:
    """Service handles text translation using the Groq API.

    Attributes:
        http_client (httpx.AsyncClient): The HTTP client for making requests.
        client (AsyncGroq): The Groq API client.

    """

    LANG_NAMES = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "pt": "Portuguese",
        "ja": "Japanese",
    }

    def __init__(self) -> None:
        """Initializes the TranslationService with Groq credentials."""
        self.http_client = httpx.AsyncClient()
        self.client = AsyncGroq(
            api_key=GROQ_API_KEY,
            http_client=self.http_client,
        )

    async def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        """Translates text from source language to target language.

        Args:
            text (str): The text to translate.
            source_lang (str): The source language code.
            target_lang (str): The target language code.

        Returns:
            str: The translated text.

        """
        # Convert "fr" -> "French" for better LLM context
        target_name = self.LANG_NAMES.get(target_lang, "English")
        system_prompt = TRANSLATION_SYSTEM_PROMPT.format(target_name=target_name)

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=1024,
            )
            content = chat_completion.choices[0].message.content
            return content if content else text
        except Exception as e:
            print(f"Groq Error: {e}")
            return text # Fallback: return original if fails
    
    async def close(self) -> None:
        """Closes the HTTP client resources."""
        await self.http_client.aclose()
