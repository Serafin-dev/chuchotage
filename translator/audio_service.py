"""Service for handling audio operations using Deepgram."""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any, Union

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    SpeakOptions,
)

from translator.constants import DEEPGRAM_API_KEY

logger = logging.getLogger(__name__)


class AudioService:
    """Handles audio transcription and synthesis using Deepgram.

    Attributes:
        client (DeepgramClient): The Deepgram client instance.

    """

    # Mapping of Language Code -> Deepgram Voice Model (TTS)
    VOICE_MAPPING: Dict[str, str] = {
        "en": "aura-asteria-en",
        "es": "aura-2-celeste-es",
        "fr": "aura-2-agathe-fr",
        "de": "aura-2-lara-de",
        "pt": "aura-asteria-en",  # Fallback for PT
    }

    def __init__(self, api_key: str = DEEPGRAM_API_KEY):
        """Initializes the AudioService with Deepgram credentials.

        Args:
            api_key (str): The Deepgram API key. Defaults to imported constant.
        """
        config = DeepgramClientOptions(options={"keepalive": "true"})
        self.client = DeepgramClient(api_key, config)

    def create_live_transcription_connection(
        self,
        source_lang: str,
        on_message_callback: Callable[[Any, Any, Any], None],
        on_error_callback: Optional[Callable[[Any, Any, Any], None]] = None,
    ) -> Any:
        """Creates and starts a live transcription connection.

        Args:
            source_lang (str): The language code of the audio source (e.g., 'es', 'en').
            on_message_callback (Callable): Callback function for transcript events.
            on_error_callback (Callable, optional): Callback function for error events.

        Returns:
            Any: The active Deepgram live connection object, or None if start failed.

        """
        try:
            connection = self.client.listen.live.v("1")

            # Register event handlers
            connection.on(LiveTranscriptionEvents.Transcript, on_message_callback)
            if on_error_callback:
                connection.on(LiveTranscriptionEvents.Error, on_error_callback)

            options = LiveOptions(
                model="nova-2",
                language=source_lang,
                smart_format=True,
                endpointing=350,
            )

            if connection.start(options) is False:
                logger.error("Failed to start Deepgram live connection.")
                return None

            return connection

        except Exception as e:
            logger.error(f"Error creating live transcription connection: {e}")
            raise

    async def synthesize_speech(self, text: str, target_lang: str) -> Optional[bytes]:
        """Converts text to speech using Deepgram TTS.

        Args:
            text (str): The text to synthesize.
            target_lang (str): The target language code to select the voice model.

        Returns:
            Optional[bytes]: The audio bytes if successful, None otherwise.

        """
        voice_model = self.VOICE_MAPPING.get(target_lang, "aura-asteria-en")
        
        options = SpeakOptions(
            model=voice_model,
            encoding="mp3",
        )

        try:
            # We use asyncio.to_thread because the SDK might be synchronous or we want to ensure non-blocking
            response = await asyncio.to_thread(
                self.client.speak.v("1").stream,
                {"text": text},
                options
            )

            # Handle different possible response types from SDK
            if hasattr(response, 'read'):
                return response.read()
            elif hasattr(response, 'stream') and hasattr(response.stream, 'read'):
                return response.stream.read()
            elif hasattr(response, 'content'):
                return response.content
            else:
                logger.error(f"Unknown response format from Deepgram TTS: {type(response)}")
                return None

        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            return None
