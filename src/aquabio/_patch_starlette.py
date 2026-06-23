"""Patch missing symbols in newer starlette versions for streamlit compatibility.

starlette >=0.35 removed DEFAULT_EXCLUDED_CONTENT_TYPES and IdentityResponder
from starlette.middleware.gzip, but streamlit <=1.58 still imports them.

Import this module BEFORE importing streamlit.
"""
from __future__ import annotations

import starlette.middleware.gzip as _gz


# ── DEFAULT_EXCLUDED_CONTENT_TYPES ──
# Streamlit uses this to extend the exclusion list with audio/video types.
_DEFAULT_TYPES: tuple[str, ...] = ("text/event-stream",)

if not hasattr(_gz, "DEFAULT_EXCLUDED_CONTENT_TYPES"):
    _gz.DEFAULT_EXCLUDED_CONTENT_TYPES = _DEFAULT_TYPES


# ── IdentityResponder ──
# Streamlit extends this class for its MediaAwareIdentityResponder.
# It's a pass-through responder that sends responses without compression.
if not hasattr(_gz, "IdentityResponder"):

    class _IdentityResponder(_gz.GZipResponder):
        """Pass-through ASGI responder (no compression)."""

        async def __call__(self, scope, receive, send):
            self.send = send
            await self.app(scope, receive, self.send_without_compression)

        async def send_without_compression(self, message):
            message_type = message["type"]
            if message_type == "http.response.start":
                self.initial_message = message
                headers = _gz.Headers(raw=self.initial_message["headers"])
                self.content_encoding_set = "content-encoding" in headers
            await self.send(message)

    _gz.IdentityResponder = _IdentityResponder  # type: ignore[attr-defined]
