"""
TEMPORARY DEVELOPMENT ENDPOINT ONLY - TO BE REMOVED AFTER INTEGRATION
"""
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.speech_service import speech_service

router = APIRouter()


class TranscribeDevRequest(BaseModel):
    audio_path: str


@router.post("/transcribe")
def dev_transcribe(request: TranscribeDevRequest):
    """
    TEMPORARY DEVELOPMENT ENDPOINT ONLY
    Manual test endpoint for SpeechService transcription.
    """
    result = speech_service.transcribe(request.audio_path)
    return result
