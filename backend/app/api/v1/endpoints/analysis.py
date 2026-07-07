import os
import base64
import json
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.schemas.analysis import ImageAnalysisRequestSchema, ImageAnalysisResponseSchema

router = APIRouter()

@router.post("/image", response_model=ImageAnalysisResponseSchema, status_code=status.HTTP_200_OK)
async def analyze_image(payload: ImageAnalysisRequestSchema):
    """
    Perform visual reasoning, OCR extraction, and object detection on an uploaded image.
    Uses Google Gemini Vision API via direct HTTP request.
    """
    # Print incoming request payload
    print(f"[DIAGNOSTIC] Incoming request payload: {payload.model_dump() if hasattr(payload, 'model_dump') else payload.__dict__}")

    # 1. Verify file exists in uploads/images directory
    filename = payload.filename
    safe_filename = os.path.basename(filename)
    image_path = Path(settings.UPLOAD_DIR) / "images" / safe_filename
    
    # Print resolved image path and whether it exists
    print(f"[DIAGNOSTIC] Resolved image path: {image_path}")
    print(f"[DIAGNOSTIC] Whether the image exists: {image_path.exists()}")

    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested image file was not found in the uploads workspace."
        )

    # 2. Check API Key configuration
    api_key = settings.GEMINI_API_KEY
    # Print whether GEMINI_API_KEY is loaded (only True/False)
    has_api_key = bool(api_key and api_key != "your_gemini_api_key_here")
    print(f"[DIAGNOSTIC] Whether GEMINI_API_KEY is loaded: {has_api_key}")

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

    # 4. Construct request payload for Gemini API
    prompt_text = (
        "Analyze this image and return a JSON object with the following fields:\n"
        "- 'caption': a concise description of what the image shows\n"
        "- 'ocr_text': a single string containing any readable text/numbers found inside the image\n"
        "- 'objects_detected': a list of key items, visual elements, or regions of interest detected\n"
        "- 'confidence': a float value between 0.0 and 1.0 representing your overall analysis confidence.\n"
        "Do not wrap your answer in any markdown markup, backticks, or other formatting. Only return raw JSON."
    )

    gemini_payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    # Use Gemini 2.5 Flash model
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    # 5. Call Gemini API asynchronously using httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(gemini_url, json=gemini_payload)
            
            # Print full Gemini HTTP response status
            print(f"[DIAGNOSTIC] Full Gemini HTTP response status: {response.status_code}")
            # Print full Gemini response body before any parsing
            print(f"[DIAGNOSTIC] Full Gemini response body: {response.text}")
            
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
            
            # Parse structured JSON from response text
            parsed_result = json.loads(content_text)
            
            # Validate output fields and provide defaults if missing
            return {
                "success": True,
                "caption": str(parsed_result.get("caption", "No description available")),
                "objects_detected": list(parsed_result.get("objects_detected", ["Image Asset"])),
                "ocr_text": str(parsed_result.get("ocr_text", "")),
                "confidence": float(parsed_result.get("confidence", 0.95))
            }

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to parse structured JSON response from Gemini model."
        )
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
