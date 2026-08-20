import pytest
import uuid
from app.services.workspace_intelligence_service import WorkspaceIntelligenceService


@pytest.mark.asyncio
async def test_workspace_summary_generation():
    test_sid = str(uuid.uuid4())
    summary = await WorkspaceIntelligenceService.get_workspace_summary(test_sid)
    assert summary is not None
    assert summary["session_id"] == test_sid
    assert "total_documents" in summary
    assert "modality_distribution" in summary
