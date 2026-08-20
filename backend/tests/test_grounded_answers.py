import pytest
from unittest.mock import AsyncMock, patch
from app.services.grounded_answer_service import GroundedAnswerService


@pytest.mark.asyncio
async def test_grounded_answer_generation():
    evidence_chunks = [
        {
            "filename": "report.pdf",
            "source_type": "pdf",
            "text": "The revenue grew by 15%.",
            "relevance_score": 0.9
        }
    ]
    citations = [
        {
            "citation_id": "cit_001",
            "filename": "report.pdf",
            "source_type": "pdf",
            "locator": "page 1",
            "relevance_score": 0.9,
            "supporting_content": "The revenue grew by 15%."
        }
    ]

    with patch("app.services.grounded_answer_service.GroundedAnswerService.generate_grounded_answer", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "answer": "Revenue grew by 15% [cit_001].",
            "citations": citations,
            "grounding_status": "grounded"
        }
        res = await GroundedAnswerService.generate_grounded_answer(
            question="How much did revenue grow?",
            evidence=evidence_chunks,
            citations=citations
        )
        assert res["grounding_status"] == "grounded"
        assert len(res["citations"]) == 1


@pytest.mark.asyncio
async def test_insufficient_evidence_response():
    resp = GroundedAnswerService._build_insufficient_evidence_response(session_id="test_sess", latency=0.01)
    assert resp["grounding_status"] == "insufficient_evidence"
    assert "provided context does not contain" in resp["answer"].lower()
