import logging
import httpx
from typing import Dict, Any
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.retriever_service import RetrieverService

logger = logging.getLogger(__name__)

class RAGService:
    """
    RAGService coordinates retrieval via RetrieverService, constructs a grounded prompt,
    invokes Gemini API, and formats structured RAG responses.
    """

    @classmethod
    async def answer_question(
        cls,
        vector_store_id: str,
        question: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Executes full RAG workflow for a user question against a vector store.
        """
        # 1. Retrieve relevant chunks using RetrieverService
        retrieved_chunks = RetrieverService.retrieve(
            vector_store_id=vector_store_id,
            question=question,
            top_k=top_k
        )

        if not retrieved_chunks:
            return {
                "success": True,
                "answer": "The requested information could not be found in the provided context.",
                "retrieved_chunks": 0,
                "sources": []
            }

        # 2. Build grounded context text
        context_blocks = []
        for idx, chunk in enumerate(retrieved_chunks, 1):
            context_blocks.append(f"Context Chunk {idx} (ID: {chunk['chunk_id']}):\n{chunk['chunk_text']}")
        
        context_text = "\n\n---\n\n".join(context_blocks)

        # 3. Build RAG prompt
        prompt = (
            "You are VisionGPT.\n\n"
            "Answer ONLY using the provided context.\n\n"
            "If the answer is not present in the context, clearly state that the information could not be found.\n\n"
            "Do not fabricate information or use outside knowledge.\n\n"
            f"Context:\n\n{context_text}\n\n"
            f"Question:\n\n{question.strip()}\n\n"
            "Answer:"
        )

        # 4. Invoke Gemini API
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your_gemini_api_key_here":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gemini API Key is not configured. Please set GEMINI_API_KEY in your environment configuration."
            )

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        gemini_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(gemini_url, json=gemini_payload)

                if response.status_code != 200:
                    err_detail = response.text
                    try:
                        err_json = response.json()
                        err_detail = err_json.get("error", {}).get("message", err_detail)
                    except Exception:
                        pass
                    logger.error(f"Gemini API returned status code {response.status_code}: {err_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Gemini AI service encountered an error while generating the response. Please try again."
                    )

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Gemini AI service is currently unavailable. Please try again."
                    )

                answer_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

        except httpx.RequestError as e:
            logger.error(f"Failed to communicate with Gemini API: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to connect to Gemini AI service. Please check your network connection and try again."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Gemini API: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong while generating your answer. Please try again."
            )

        # 5. Format sources list (preview max 100 chars, chunk_id, score)
        sources = []
        for chunk in retrieved_chunks:
            text_preview = chunk["chunk_text"][:100]
            sources.append({
                "chunk_id": chunk["chunk_id"],
                "score": chunk["similarity_score"],
                "preview": text_preview
            })

        return {
            "success": True,
            "answer": answer_text,
            "retrieved_chunks": len(retrieved_chunks),
            "sources": sources
        }
