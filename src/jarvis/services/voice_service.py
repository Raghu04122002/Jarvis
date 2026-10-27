"""Voice service — Whisper STT and ElevenLabs TTS."""

import logging

import httpx

from jarvis.config import VoiceConfig

logger = logging.getLogger(__name__)


class VoiceServiceError(Exception):
    """Raised when a voice API call fails."""


class VoiceService:
    def __init__(self, config: VoiceConfig) -> None:
        self._config = config

    @property
    def stt_available(self) -> bool:
        return self._config.stt_enabled and bool(self._config.whisper_api_key)

    @property
    def tts_available(self) -> bool:
        return self._config.tts_enabled and bool(self._config.elevenlabs_api_key)

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcribe audio bytes using OpenAI Whisper API."""
        if not self.stt_available:
            raise VoiceServiceError("STT is not configured — set OPENAI_API_KEY")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._config.whisper_api_key}"},
                data={"model": self._config.whisper_model},
                files={"file": (filename, audio_bytes)},
            )

        if resp.status_code != 200:
            raise VoiceServiceError(f"Whisper API error {resp.status_code}: {resp.text}")

        return resp.json()["text"]

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to speech using ElevenLabs API. Returns mp3 bytes."""
        if not self.tts_available:
            raise VoiceServiceError("TTS is not configured — set ELEVENLABS_API_KEY")

        voice_id = self._config.elevenlabs_voice_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": self._config.elevenlabs_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": self._config.elevenlabs_model_id,
                },
            )

        if resp.status_code != 200:
            raise VoiceServiceError(f"ElevenLabs API error {resp.status_code}: {resp.text}")

        return resp.content
