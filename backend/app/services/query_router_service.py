import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class QueryRouterService:
    """
    Intelligent Query Router Service for VisionGPT.
    Classifies user queries into query_types ('single_source', 'multimodal', 'workspace',
    'comparison', 'unsupported') based on query intent, session context, media types,
    and document filters, and dispatches to the most appropriate existing pipeline.
    """

    WORKSPACE_PATTERNS = [
        r"\bworkspace\b", r"\ball documents?\b", r"\bevery document\b",
        r"\ball files?\b", r"\bworkspace summary\b", r"\bsession summary\b",
        r"\bacross documents?\b", r"\bacross files?\b"
    ]

    COMPARISON_PATTERNS = [
        r"\bcompare\b", r"\bcontrast\b", r"\bdifference\b", r"\bdiffer\b",
        r"\bagree with\b", r"\bdisagree with\b", r"\bversus\b", r"\bvs\.?\b",
        r"\bcomparison\b", r"\bhow does .* compare\b"
    ]

    MULTIMODAL_PATTERNS = [
        r"\bpdf and audio\b", r"\baudio and pdf\b", r"\bpdf and video\b",
        r"\bvideo and pdf\b", r"\baudio and video\b", r"\btranscript and pdf\b",
        r"\bvideo and audio\b", r"\bimages? and text\b"
    ]

    SINGLE_SOURCE_PATTERNS = [
        r"\bthis pdf\b", r"\bthis document\b", r"\bthis audio\b", r"\bthis video\b",
        r"\bthis recording\b", r"\bpage \d+\b", r"\btranscript\b", r"\bthis file\b"
    ]

    @classmethod
    def classify_query(
        cls,
        question: str,
        session_id: Optional[Union[str, Any]] = None,
        vector_store_dir: Optional[Union[str, Path]] = None,
        vector_store_id: Optional[str] = None,
        source_filters: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Classifies user query intent and selects the optimal execution pipeline.
        Returns routing metadata containing query_type, selected_pipeline, reason, and confidence.
        """
        if not question or not question.strip():
            return {
                "query_type": "unsupported",
                "selected_pipeline": "insufficient_evidence",
                "reason": "Empty or whitespace question provided.",
                "confidence": 1.0
            }

        q_lower = question.strip().lower()

        # Rule 1: Explicit comparison patterns -> 'comparison' (routed to workspace intelligence)
        if any(re.search(pat, q_lower) for pat in cls.COMPARISON_PATTERNS):
            return {
                "query_type": "comparison",
                "selected_pipeline": "workspace_intelligence",
                "reason": "Query contains comparison keywords targeting cross-source analysis.",
                "confidence": 0.92
            }

        # Rule 2: Explicit workspace wide patterns -> 'workspace'
        if any(re.search(pat, q_lower) for pat in cls.WORKSPACE_PATTERNS):
            return {
                "query_type": "workspace",
                "selected_pipeline": "workspace_intelligence",
                "reason": "Query targets workspace-wide analysis across all session documents.",
                "confidence": 0.90
            }

        # Rule 3: Explicit cross-modal patterns -> 'multimodal'
        if any(re.search(pat, q_lower) for pat in cls.MULTIMODAL_PATTERNS):
            return {
                "query_type": "multimodal",
                "selected_pipeline": "multimodal_retriever",
                "reason": "Query explicitly references multiple media types (PDF, Audio, Video).",
                "confidence": 0.95
            }

        # Rule 4: Single vector store dir provided without session_id -> 'single_source'
        if vector_store_dir is not None and not session_id:
            return {
                "query_type": "single_source",
                "selected_pipeline": "local_rag",
                "reason": "Target vector_store_dir provided for direct document retrieval.",
                "confidence": 0.95
            }

        # Rule 5: Explicit single source mention -> 'single_source'
        if any(re.search(pat, q_lower) for pat in cls.SINGLE_SOURCE_PATTERNS):
            return {
                "query_type": "single_source",
                "selected_pipeline": "local_rag" if vector_store_dir else "multimodal_retriever",
                "reason": "Query references a single specific file or document context.",
                "confidence": 0.85
            }

        # Rule 6: Session provided with multiple source filters -> 'multimodal'
        if session_id and source_filters and len(source_filters) > 1:
            return {
                "query_type": "multimodal",
                "selected_pipeline": "multimodal_retriever",
                "reason": "Multiple document or media_type filters passed for session.",
                "confidence": 0.88
            }

        # Rule 7: Fallback safe routing
        if session_id:
            return {
                "query_type": "workspace",
                "selected_pipeline": "workspace_intelligence",
                "reason": "Session context present; safely defaulting to workspace intelligence pipeline.",
                "confidence": 0.75
            }

        return {
            "query_type": "single_source",
            "selected_pipeline": "local_rag",
            "reason": "Defaulting safely to single-source RAG pipeline.",
            "confidence": 0.70
        }
