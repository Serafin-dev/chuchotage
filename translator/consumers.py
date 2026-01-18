"""WebSocket Consumer for real-time translation and audio streaming."""

import json
import asyncio
import logging
from urllib.parse import parse_qs
from typing import Dict, Any, Optional

from channels.generic.websocket import AsyncWebsocketConsumer

from .translation_service import TranslationService
from .audio_service import AudioService

logger = logging.getLogger(__name__)


class TranslatorConsumer(AsyncWebsocketConsumer):
    """Consumer that handles real-time translation and audio streaming.

    Attributes:
        room_name (str): The name of the room.
        room_group_name (str): The group name for the channel layer.
        source_lang (str): The language spoken by the user (input).
        target_lang (str): The language the user wants to hear (output).
        app_loop (asyncio.AbstractEventLoop): The running event loop.
        translator (TranslationService): Service for text translation.
        audio_service (AudioService): Service for speech-to-text and text-to-speech.
        dg_connection (Any): The active Deepgram Live connection.
    """

    async def connect(self) -> None:
        """Handles the WebSocket connection event.

        Parses query parameters, joins the channel group, initializes services,
        and establishes the connection to the STT service.

        """
        try:
            # 1. Parse Parameters
            self._parse_query_params()
            
            # 2. Join Group
            # We join a single global group for the room. Everyone routes/translates locally.
            self.room_group_name = f"room_{self.room_name}_global"
            logger.info(
                "🔗 Connected to Room: %s | Source: %s -> Target: %s",
                self.room_group_name, self.source_lang, self.target_lang
            )

            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()

            # 3. Initialize Services
            self.app_loop = asyncio.get_running_loop()
            self.translator = TranslationService()
            self.audio_service = AudioService()

            # 4. Setup Deepgram STT
            self.dg_connection = self.audio_service.create_live_transcription_connection(
                source_lang=self.source_lang,
                on_message_callback=self._on_speech_transcript,
                on_error_callback=self._on_speech_error
            )

            if not self.dg_connection:
                logger.error("Failed to establish Deepgram connection. Closing WebSocket.")
                await self.close()

        except Exception as e:
            logger.error("❌ Error during connection: %s", e)
            await self.close()

    async def disconnect(self, close_code: int) -> None:
        """Handles the WebSocket disconnection event.

        Args:
            close_code (int): The code indicating why the connection was closed.

        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        if hasattr(self, 'dg_connection') and self.dg_connection:
            try:
                self.dg_connection.finish()
            except Exception:
                pass
        
        if hasattr(self, 'translator') and hasattr(self.translator, 'close'):
            await self.translator.close()

    async def receive(self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None) -> None:
        """Handles incoming data from the WebSocket.

        Forwards binary audio data to the Deepgram connection.

        Args:
            text_data (Optional[str]): Text data received (unused).
            bytes_data (Optional[bytes]): Binary data (audio) received.

        """
        if bytes_data and hasattr(self, 'dg_connection') and self.dg_connection:
            self.dg_connection.send(bytes_data)

    def _on_speech_transcript(self, connection: Any, result: Any, **kwargs: Any) -> None:
        """Callback for Deepgram transcription events.

        Checks if the transcript is final and broadcasts it to the room.

        Args:
             connection (Any): The connection object.
             result (Any): The result object containing the transcript.
             **kwargs (Any): Additional arguments.
        """
        is_final = result.is_final
        sentence = result.channel.alternatives[0].transcript

        if is_final and len(sentence.strip()) > 0:
            # When I speak, I only broadcast the ORIGINAL TEXT to the room.
            if hasattr(self, 'app_loop') and self.app_loop:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_original_to_room(sentence),
                    self.app_loop
                )

    def _on_speech_error(self, connection: Any, error: Any, **kwargs: Any) -> None:
        """Callback for Deepgram error events."""
        logger.error("Deepgram Error: %s", error)

    async def broadcast_original_to_room(self, text: str) -> None:
        """Broadcasts the original spoken text to the channel group.

        Does not translate or generate audio at this stage. It sends a message
        that will be handled by `chat_message` for all participants.

        Args:
            text (str): The text spoken by the user.
        """
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",          # Calls the chat_message method on receivers
                "original_text": text,
                "source_lang": self.source_lang, # "I am speaking [source_lang]"
                "sender_channel_name": self.channel_name
            }
        )

    async def chat_message(self, event: Dict[str, Any]) -> None:
        """Handles chat messages received from the group.

        Triggers self-echo for the sender or translation and TTS for receivers.

        Args:
            event (Dict[str, Any]): The event data containing the message.
        """
        original_text = event.get("original_text", "")
        sender_lang = event.get("source_lang", "es")
        sender_channel = event.get("sender_channel_name")

        # A. Self-Mute / Echo (Sender logic)
        if sender_channel == self.channel_name:
            # Sender sees the text but hears no audio/translation
            await self._send_transcription_update(
                text=original_text,
                translation="",
                lang=sender_lang
            )
            return

        # B. Translation & TTS Logic (Receiver logic)
        # Message comes in 'sender_lang', I want 'self.target_lang'
        
        try:
            # 1. Translate (Sender's Language -> My Target Language)
            translated_text = await self.translator.translate(
                original_text, 
                source_lang=sender_lang, 
                target_lang=self.target_lang
            )

            # 2. Generate Audio (TTS) in My Target Language
            audio_bytes = await self.audio_service.synthesize_speech(
                translated_text,
                target_lang=self.target_lang
            )

            # 3. Send to My Frontend
            if audio_bytes:
                # First, metadata
                await self._send_transcription_update(
                    text=original_text,
                    translation=translated_text,
                    lang=sender_lang
                )
                # Second, audio
                await self.send(bytes_data=audio_bytes)

        except Exception as e:
            logger.error("❌ Error processing translation/TTS for receiver: %s", e)

    async def _send_transcription_update(self, text: str, translation: str, lang: str) -> None:
        """Helper to send JSON transcription/translation updates to the frontend.
        
        Args:
            text: The original text.
            translation: The translated text.
            lang: The language code of the original text.

        """
        await self.send(text_data=json.dumps({
            "type": "transcription",
            "text": text,
            "translation": translation,
            "lang": lang
        }))

    def _parse_query_params(self) -> None:
        """Extracts room name and languages from the WebSocket scope."""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        
        self.source_lang = params.get('source', ['es'])[0] # Default to Spanish
        self.target_lang = params.get('target', ['en'])[0] # Default to English
