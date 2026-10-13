"""
api/routes_voice.py
FastAPI router for Speech-to-Text (Whisper API) voice note processing, intent extraction,
and automatic task rescheduling.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Optional

from core import voice_processor

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceTextModel(BaseModel):
    text: str


@router.post("/process-audio")
async def process_audio_file(file: UploadFile = File(...)):
    """
    Accepts audio recording (.webm, .wav, .mp3), transcribes with Whisper API,
    extracts intent (expense, task, rescheduling, sick child), updates SQLite,
    and returns actions taken.
    """
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file uploaded.")

        transcript = voice_processor.transcribe_audio(audio_bytes, filename=file.filename or "voice.webm")
        result = voice_processor.process_voice_intent(transcript)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")


@router.post("/process-text")
def process_voice_text(item: VoiceTextModel):
    """
    Direct text endpoint for processing voice note transcripts or simulated voice input.
    """
    if not item.text or not item.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    result = voice_processor.process_voice_intent(item.text.strip())
    return {"status": "success", "data": result}
