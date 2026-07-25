import os
import base64
import json
import logging
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.schemas.analysis import ImageAnalysisRequestSchema, ImageAnalysisResponseSchema

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/image", response_model=ImageAnalysisResponseSchema, status_code=status.HTTP_200_OK)
async def analyze_image(payload: ImageAnalysisRequestSchema):
    """
    Perform conversational visual reasoning on an uploaded image with a user query and history.
    Uses Google Gemini Vision API via direct HTTP request.
    """
    logger.debug(f"Incoming request payload: {payload.model_dump() if hasattr(payload, 'model_dump') else payload.__dict__}")

    # 1. Verify file exists in uploads/images directory
    filename = payload.filename
    safe_filename = os.path.basename(filename)
    image_path = Path(settings.UPLOAD_DIR) / "images" / safe_filename
    
    logger.debug(f"Resolved image path: {image_path}, exists: {image_path.exists()}")

    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested image file was not found in the uploads workspace."
        )

    # 2. Check API Key configuration
    api_key = settings.GEMINI_API_KEY
    has_api_key = bool(api_key and api_key != "your_gemini_api_key_here")
    logger.debug(f"Whether GEMINI_API_KEY is loaded: {has_api_key}")

    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API Key is not configured. Please set the GEMINI_API_KEY environment variable in your .env file."
        )

    # 3. Read image file and encode to base64
    try:
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read image file: {str(e)}"
        )

    # Detect mime type from file extension
    ext = os.path.splitext(safe_filename)[1].lower()
    mime_type = "image/png"
    if ext in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif ext == ".webp":
        mime_type = "image/webp"

    # 4. Construct request payload for Gemini API with custom conversational prompt instructions
    system_instruction = (
        "You are VisionGPT.\n\n"
        "Use both the uploaded image and previous conversation.\n\n"
        "Answer naturally and accurately.\n\n"
        "Never invent information.\n\n"
        "If the image cannot answer the question, clearly say so."
    )
    
    # Build contents history array mapping "assistant" -> "model" roles
    contents = []
    first_user_processed = False
    
    for msg in payload.history:
        role = "user" if msg.role == "user" else "model"
        parts = []
        
        # Attach base64 image data to the very first user turn
        if role == "user" and not first_user_processed:
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64_image
                }
            })
            first_user_processed = True
            
        parts.append({"text": msg.content})
        contents.append({
            "role": role,
            "parts": parts
        })
        
    # If history didn't contain any user turns or is empty
    if not first_user_processed:
        contents.append({
            "role": "user",
            "parts": [
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": base64_image
                    }
                },
                {"text": payload.user_prompt}
            ]
        })
    else:
        # Append the latest user query as the final turn
        contents.append({
            "role": "user",
            "parts": [{"text": payload.user_prompt}]
        })

    gemini_payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [
                {"text": system_instruction}
            ]
        }
    }

    # Use Gemini 2.5 Flash model
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    # 5. Call Gemini API asynchronously using httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(gemini_url, json=gemini_payload)
            
            logger.debug(f"Gemini HTTP response status: {response.status_code}")
            logger.debug(f"Gemini response body: {response.text}")
            
            if response.status_code != 200:
                err_detail = response.text
                try:
                    err_json = response.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                except ValueError:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Gemini API returned an error: {err_detail}"
                )

            data = response.json()
            
            candidates = data.get("candidates", [])
            if not candidates:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Gemini API returned no analysis candidates."
                )
                
            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            
            return {
                "success": True,
                "answer": content_text
            }

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to communicate with Gemini API: {str(e)}"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during image reasoning: {str(e)}"
        )
