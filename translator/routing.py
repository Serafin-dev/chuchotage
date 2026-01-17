"""WebSocket routing for the translator app."""
# translator/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Ahora la URL espera un nombre de sala: ws://.../ws/translator/nombre_sala/
    re_path(r'ws/translator/(?P<room_name>\w+)/$', consumers.TranslatorConsumer.as_asgi()),
]