"""Voice API routes — STT, TTS, and full voice chat pipeline."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import get_orchestrator, get_session, get_voice_service
from jarvis.services.voice_service import VoiceService, VoiceServiceError

router = APIRouter(prefix="/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    text: str


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile,
    voice: VoiceService = Depends(get_voice_service),
) -> dict[str, str]:
    """Transcribe uploaded audio to text via Whisper."""
    if not voice.stt_available:
        raise HTTPException(status_code=503, detail="STT not configured")

    audio_bytes = await audio.read()
    filename = audio.filename or "audio.webm"

    try:
        text = await voice.transcribe(audio_bytes, filename)
    except VoiceServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {"text": text}


@router.post("/synthesize")
async def synthesize(
    req: SynthesizeRequest,
    voice: VoiceService = Depends(get_voice_service),
) -> Response:
    """Synthesize text to speech via ElevenLabs. Returns audio/mpeg."""
    if not voice.tts_available:
        raise HTTPException(status_code=503, detail="TTS not configured")

    try:
        audio_bytes = await voice.synthesize(req.text)
    except VoiceServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/chat")
async def voice_chat(
    audio: UploadFile,
    voice: VoiceService = Depends(get_voice_service),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Full voice pipeline: audio in -> STT -> Orchestrator -> TTS -> audio out."""
    if not voice.stt_available:
        raise HTTPException(status_code=503, detail="STT not configured")

    audio_bytes = await audio.read()
    filename = audio.filename or "audio.webm"

    try:
        transcript = await voice.transcribe(audio_bytes, filename)
    except VoiceServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    orchestrator = get_orchestrator()
    result = await orchestrator.chat(transcript, session=session)
    reply_text = result.get("answer") or result.get("message", "")

    headers = {"X-Transcript": transcript}

    if voice.tts_available and reply_text:
        try:
            reply_audio = await voice.synthesize(reply_text)
        except VoiceServiceError:
            return Response(
                content=reply_text.encode(),
                media_type="text/plain",
                headers=headers,
            )
        return Response(
            content=reply_audio,
            media_type="audio/mpeg",
            headers=headers,
        )

    return Response(
        content=reply_text.encode(),
        media_type="text/plain",
        headers=headers,
    )
