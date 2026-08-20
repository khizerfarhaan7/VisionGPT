import pytest
from unittest.mock import AsyncMock, patch
from app.services.query_router_service import QueryRouterService
from app.services.evidence_citation_service import EvidenceCitationService
from app.services.grounded_answer_service import GroundedAnswerService
from app.core.model_manager import model_manager
from app.core.config import settings


def test_final_system_architecture_defaults():
    assert settings.VISIONGPT_PROFILE in ("local", "high_quality", "custom")
    assert settings.MAX_CONCURRENT_JOBS == 1
    assert settings.MAX_UPLOAD_SIZE_MB >= 1
    assert settings.SECURITY_RATE_LIMIT_ENABLED is True


def test_zero_models_loaded_at_startup():
    assert len(model_manager._models) == 0, "No AI model weights should be loaded at application startup."


@pytest.mark.asyncio
async def test_final_rag_pipeline_integration_chain():
    # 1. Query Routing Classification
    query = "Compare the financial growth in the Q3 PDF report with the audio earnings call transcript."
    route_meta = QueryRouterService.classify_query(question=query)
    assert route_meta["query_type"] in ("comparison", "multimodal", "workspace", "single_source")
    assert "selected_pipeline" in route_meta

    # 2. Synthetic Evidence & Citations
    synthetic_evidence = [
        {
            "chunk_id": "pdf_c1",
            "source_type": "pdf",
            "document_id": "doc_pdf_01",
            "filename": "Q3_Report.pdf",
            "metadata": {"page": 4},
            "text": "Q3 net revenue reached $4.2M, representing 18% YoY growth.",
            "relevance_score": 0.95
        },
        {
            "chunk_id": "audio_c1",
            "source_type": "audio",
            "document_id": "doc_audio_01",
            "filename": "Earnings_Call.mp3",
            "metadata": {"start_time": 120.5, "end_time": 145.0},
            "text": "CEO confirmed Q3 revenue target was surpassed by $500k.",
            "relevance_score": 0.88
        }
    ]

    citations = EvidenceCitationService.build_citations(synthetic_evidence)
    assert len(citations) == 2
    assert citations[0]["locator"] == "page 4"
    assert "02:00" in citations[1]["locator"]

    # 3. Grounded Answer Generation
    with patch.object(GroundedAnswerService, "generate_grounded_answer", new_callable=AsyncMock) as mock_answer:
        mock_answer.return_value = {
            "success": True,
            "answer": "Q3 net revenue grew 18% YoY reaching $4.2M [cit_001], surpassing targets by $500k [cit_002].",
            "citations": citations,
            "evidence_count": len(synthetic_evidence),
            "sources_used": ["pdf", "audio"],
            "confidence": 0.92,
            "insufficient_evidence": False,
            "model_provider": "ollama",
            "model_name": "qwen2.5:3b",
            "session_id": "sess_final_001"
        }

        resp = await GroundedAnswerService.generate_grounded_answer(
            question=query,
            evidence=synthetic_evidence,
            citations=citations,
            session_id="sess_final_001"
        )

        assert resp["success"] is True
        assert resp["insufficient_evidence"] is False
        assert len(resp["citations"]) == 2
        assert resp["confidence"] > 0.8
        assert resp["session_id"] == "sess_final_001"


def test_final_openapi_routes_present(client):
    schema = client.app.openapi()
    paths = schema.get("paths", {})

    required_routes = [
        "/",
        "/api/v1/health",
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/metrics",
        "/api/v1/jobs",
        "/api/v1/chat/query",
        "/api/v1/workspace/query",
        "/api/v1/pdf/index",
        "/api/v1/audio/transcribe",
        "/api/v1/video/index"
    ]

    for route in required_routes:
        assert route in paths, f"Required OpenAPI route '{route}' missing in FastAPI app."

    # Zero models loaded after OpenAPI inspection
    assert len(model_manager._models) == 0
