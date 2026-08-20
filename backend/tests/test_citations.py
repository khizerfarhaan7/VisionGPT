import pytest
from app.services.evidence_citation_service import EvidenceCitationService


def test_pdf_citation_generation():
    chunks = [
        {
            "document_id": "doc_pdf_1",
            "filename": "report.pdf",
            "media_type": "pdf",
            "content": "Financial revenue grew by 18% in Q3.",
            "relevance_score": 0.92,
            "metadata": {"page": 5}
        }
    ]
    citations = EvidenceCitationService.build_citations(chunks)
    assert len(citations) == 1
    c = citations[0]
    assert c["citation_id"].startswith("cite_")
    assert c["source_type"] == "pdf"
    assert c["locator"] == "page 5"
    assert c["relevance_score"] == 0.92


def test_audio_citation_generation():
    chunks = [
        {
            "document_id": "doc_audio_1",
            "filename": "interview.mp3",
            "media_type": "audio",
            "content": "The speaker discusses product strategy.",
            "relevance_score": 0.88,
            "metadata": {"start_time": 12.5, "end_time": 25.0}
        }
    ]
    citations = EvidenceCitationService.build_citations(chunks)
    assert len(citations) == 1
    c = citations[0]
    assert c["source_type"] == "audio"
    assert "00:12" in c["locator"]


def test_video_citation_generation():
    chunks = [
        {
            "document_id": "doc_video_1",
            "filename": "lecture.mp4",
            "media_type": "video",
            "content": "Visual slide showing architecture diagram.",
            "relevance_score": 0.95,
            "metadata": {"start_time": 120.0, "end_time": 150.0}
        }
    ]
    citations = EvidenceCitationService.build_citations(chunks)
    assert len(citations) == 1
    c = citations[0]
    assert c["source_type"] == "video"
    assert "02:00" in c["locator"]


def test_citation_deduplication():
    chunks = [
        {
            "document_id": "doc_1",
            "filename": "report.pdf",
            "media_type": "pdf",
            "content": "Duplicate chunk 1",
            "metadata": {"page": 1}
        },
        {
            "document_id": "doc_1",
            "filename": "report.pdf",
            "media_type": "pdf",
            "content": "Duplicate chunk 2",
            "metadata": {"page": 1}
        }
    ]
    citations = EvidenceCitationService.build_citations(chunks)
    assert len(citations) == 1
