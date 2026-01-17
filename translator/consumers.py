
import json
import asyncio
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    SpeakOptions,
)

from translator.constants import DEEPGRAM_API_KEY
from .translation_service import TranslationService

# Mapeo de Idioma -> Voz de Deepgram (TTS)
VOICE_MAPPING = {
    "en": "aura-asteria-en",    
    "es": "aura-2-celeste-es",  
    "fr": "aura-2-agathe-fr",   
    "de": "aura-2-lara-de",     
    "pt": "aura-asteria-en",    # Fallback para PT
}

class TranslatorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Obtener parámetros
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        
        self.source_lang = params.get('source', ['es'])[0] # Lo que hablo
        self.target_lang = params.get('target', ['en'])[0] # Lo que quiero escuchar

        # 2. CAMBIO CLAVE: Unirse a un ÚNICO grupo general para la sala
        # Ya no nos unimos a "room_X_english", sino a "room_X_global".
        # Todos escuchan todo, y filtran localmente.
        self.room_group_name = f"room_{self.room_name}_global"

        print(f"🔗 Conectado a Sala: {self.room_group_name} | Soy: {self.source_lang} -> Quiero: {self.target_lang}")

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # 3. Inicializar Servicios
        self.app_loop = asyncio.get_running_loop()
        self.translator = TranslationService()

        try:
            # Config Deepgram STT (Input)
            config = DeepgramClientOptions(options={"keepalive": "true"})
            self.deepgram = DeepgramClient(DEEPGRAM_API_KEY, config)
            self.dg_connection = self.deepgram.listen.live.v("1")

            def on_message(self_dg, result, **kwargs):
                is_final = result.is_final
                sentence = result.channel.alternatives[0].transcript
                
                if is_final and len(sentence.strip()) > 0:
                    # Cuando hablo, solo envío el TEXTO ORIGINAL a la sala
                    if hasattr(self, 'app_loop') and self.app_loop:
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast_original_to_room(sentence),
                            self.app_loop
                        )

            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

            options = LiveOptions(
                model="nova-2", 
                language=self.source_lang, 
                smart_format=True,
                endpointing=350,
            )
            
            if self.dg_connection.start(options) is False:
                await self.close()
                return

        except Exception as e:
            print(f"❌ Error connect: {e}")
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        if hasattr(self, 'dg_connection') and self.dg_connection:
            try: self.dg_connection.finish()
            except: pass

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            self.dg_connection.send(bytes_data)

    # ---------------------------------------------------------
    # 1. EL ORADOR: Solo avisa "Dije esto en este idioma"
    # ---------------------------------------------------------
    async def broadcast_original_to_room(self, text):
        """
        Envía el texto crudo a Redis. No traduce. No genera audio.
        """
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",          # Llama al método chat_message de LOS DEMÁS
                "original_text": text,
                "source_lang": self.source_lang, # "Soy ES"
                "sender_channel_name": self.channel_name
            }
        )

    # ---------------------------------------------------------
    # 2. EL OYENTE (Receiver): Aquí ocurre la magia personalizada
    # ---------------------------------------------------------
    async def chat_message(self, event):
        """
        Cada usuario en la sala recibe el evento y decide qué hacer con él.
        """
        # A. FILTRO ANTI-ECO (Self-Mute)
        if event["sender_channel_name"] == self.channel_name:
            # Si fui yo quien habló, mando el texto para verlo en pantalla, 
            # pero NO genero audio ni traduzco.
            await self.send(text_data=json.dumps({
                "type": "transcription",
                "text": event["original_text"],
                "translation": "", # No me traduzco a mi mismo
                "lang": event["source_lang"]
            }))
            return

        # B. LÓGICA DE TRADUCCIÓN PERSONALIZADA
        # El mensaje viene en 'source_lang'. Yo quiero 'self.target_lang'.
        
        try:
            # 1. Traducir (Del idioma del Orador -> A MI idioma deseado)
            # Nota: Si el orador habló en Inglés y yo quiero Inglés, Groq
            # puede optimizar o simplemente corregir gramática, pero pasamos por el flujo igual.
            translated_text = await self.translator.translate(
                event["original_text"], 
                source_lang=event["source_lang"], 
                target_lang=self.target_lang
            )

            # 2. Generar Audio (TTS) en MI idioma deseado
            voice_model = VOICE_MAPPING.get(self.target_lang, "aura-asteria-en")
            
            options = SpeakOptions(
                model=voice_model,
                encoding="mp3",
                # container="none" # Eliminado para MP3
            )
            
            # Llamada a Deepgram TTS
            response = await asyncio.to_thread(
                self.deepgram.speak.v("1").stream, 
                {"text": translated_text},
                options
            )
            
            if hasattr(response, 'read'): audio_bytes = response.read()
            elif hasattr(response, 'stream'): audio_bytes = response.stream.read()
            else: audio_bytes = response.content

            # 3. Enviar a mi Frontend
            if audio_bytes:
                # Primero metadatos
                await self.send(text_data=json.dumps({
                    "type": "transcription",
                    "text": event["original_text"],
                    "translation": translated_text,
                    "lang": event["source_lang"]
                }))
                # Segundo audio
                await self.send(bytes_data=audio_bytes)

        except Exception as e:
            print(f"❌ Error procesando traducción para oyente: {e}")