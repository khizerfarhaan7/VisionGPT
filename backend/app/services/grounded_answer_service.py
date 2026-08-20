import logging
import time
from typing import Any, Dict, List, Optional, Union
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GroundedAnswerService:
    """
    Multimodal Grounded Answer Engine for VisionGPT.
    Generates a single grounded answer strictly from supplied evidence and citations,
    calculates a lightweight confidence metric, detects insufficient evidence,
    and supports both Local (Ollama) and Cloud (Gemini) LLM inference.
    """

    INSUFFICIENT_EVIDENCE_ANSWER = (
        "The provided context does not contain sufficient information to answer your question."
    )

    @classmethod
    async def generate_grounded_answer(
        cls,
        question: str,
        evidence: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
        mode: str = "local",
        session_id: Optional[Any] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generates a grounded answer from retrieved multimodal evidence and structured citations.
        """
        start_time = time.time()
        question_clean = question.strip()

        # 1. Check for Insufficient Evidence State
        if not evidence or not citations:
            logger.info("GroundedAnswerService: No evidence/citations provided -> Returning insufficient evidence state.")
            return cls._build_insufficient_evidence_response(
                session_id=session_id,
                latency=round(time.time() - start_time, 3)
            )

        # Check average relevance score threshold
        avg_rel = sum(e.get("relevance_score", 0.0) for e in evidence) / len(evidence)
        if avg_rel < 0.15:
            logger.info(f"GroundedAnswerService: Low relevance score ({avg_rel:.4f}) -> Returning insufficient evidence state.")
            return cls._build_insufficient_evidence_response(
                session_id=session_id,
                latency=round(time.time() - start_time, 3)
            )

        # 2. Calculate Confidence Metric
        distinct_sources = len(set(e.get("filename", e.get("document_id", "")) for e in evidence))
        confidence = round(
            0.5 * avg_rel +
            0.3 * min(distinct_sources / 3.0, 1.0) +
            0.2 * min(len(evidence) / 4.0, 1.0),
            2
        )

        # 3. Build Grounded Context & Prompt
        context_blocks = []
        for cite in citations:
            cite_tag = f"[{cite.get('citation_id', 'cite')}]"
            fn = cite.get("filename", "Source")
            loc = cite.get("locator", "unknown")
            snippet = cite.get("supporting_content", "").strip()
            context_blocks.append(f"{cite_tag} Source: {fn} ({loc})\nContent: {snippet}")

        grounded_context = "\n\n---\n\n".join(context_blocks)

        system_prompt = (
            "You are VisionGPT, an advanced multimodal AI assistant.\n"
            "Answer the question strictly using the provided evidence blocks.\n"
            "Follow these strict directives:\n"
            "1. Base your answer ONLY on the supplied evidence. Do not assume or invent facts.\n"
            "2. When stating facts, cite your sources using the exact citation tags provided in brackets (e.g. [cite_1], [cite_2]).\n"
            "3. If the provided evidence is insufficient to answer the question, state clearly: "
            f"'{cls.INSUFFICIENT_EVIDENCE_ANSWER}'\n"
            "4. Keep answers concise, completa, and well-structured."
        )

        user_prompt = (
            f"Retrieved Evidence:\n\n{grounded_context}\n\n"
            f"User Question: {question_clean}\n\n"
            "Grounded Answer:"
        )

        # 4. Generate Answer via Selected Provider
        provider = mode.lower().strip()
        if provider not in ("local", "cloud"):
            provider = "local"

        answer_text = ""
        model_name = settings.OLLAMA_MODEL if provider == "local" else settings.GEMINI_MODEL

        try:
            if provider == "local":
                answer_text = await cls._generate_ollama(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    history=history or []
                )
            else:
                answer_text = await cls._generate_gemini(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )
        except Exception as gen_err:
            logger.error(f"GroundedAnswerService: Provider '{provider}' generation failed: {gen_err}", exc_info=True)
            # Fallback message
            answer_text = (
                f"Generated from retrieved evidence across {len(citations)} source(s):\n\n" +
                "\n".join([f"• {c.get('filename')} ({c.get('locator')}): {c.get('supporting_content')}" for c in citations[:3]])
            )

        latency = round(time.time() - start_time, 3)

        sources_used = []
        seen_src = set()
        for c in citations:
            doc_id = c.get("document_id")
            if doc_id and doc_id not in seen_src:
                seen_src.add(doc_id)
                sources_used.append({
                    "document_id": doc_id,
                    "filename": c.get("filename"),
                    "source_type": c.get("source_type")
                })

        logger.info(
            f"GroundedAnswerService: Answer generated. Provider='{provider}' Model='{model_name}' "
            f"Confidence={confidence} EvidenceCount={len(evidence)} Latency={latency}s"
        )

        return {
            "success": True,
            "answer": answer_text,
            "citations": citations,
            "evidence_count": len(evidence),
            "sources_used": sources_used,
            "confidence": confidence,
            "insufficient_evidence": False,
            "model_provider": provider,
            "model_name": model_name,
            "session_id": str(session_id) if session_id else None
        }

    @classmethod
    def _build_insufficient_evidence_response(
        cls,
        session_id: Optional[Any],
        latency: float
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "answer": cls.INSUFFICIENT_EVIDENCE_ANSWER,
            "citations": [],
            "evidence_count": 0,
            "sources_used": [],
            "confidence": 0.0,
            "insufficient_evidence": True,
            "model_provider": "none",
            "model_name": "none",
            "session_id": str(session_id) if session_id else None
        }

    @classmethod
    async def _generate_ollama(
        cls,
        system_prompt: str,
        user_prompt: str,
        history: List[Dict[str, Any]]
    ) -> str:
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        messages = [{"role": "system", "content": system_prompt}]

        # Add recent conversation turns
        for msg in (history[-3:] if history else []):
            role = "user" if getattr(msg, "role", "user") == "user" else "assistant"
            content = getattr(msg, "content", str(msg))
            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2}
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
            else:
                logger.warning(f"Ollama return status {resp.status_code}: {resp.text}")
                raise RuntimeError(f"Ollama status {resp.status_code}")

    @classmethod
    async def _generate_gemini(
        cls,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your_gemini_api_key_here":
            raise RuntimeError("Gemini API key is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": full_prompt}]}]
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            raise RuntimeError(f"Gemini API returned status {resp.status_code}")
