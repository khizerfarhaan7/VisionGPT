import pytest
from app.services.query_router_service import QueryRouterService


def test_query_router_classification_single_source():
    info = QueryRouterService.classify_query("Summarize this document")
    assert info["query_type"] in ("single_source", "multimodal", "workspace")
    assert "selected_pipeline" in info


def test_query_router_classification_multimodal():
    info = QueryRouterService.classify_query("Compare pdf and audio files")
    assert info["query_type"] in ("multimodal", "comparison", "workspace")


def test_query_router_classification_workspace():
    info = QueryRouterService.classify_query("Give me a workspace summary of all documents")
    assert info["query_type"] == "workspace"


def test_query_router_classification_comparison():
    info = QueryRouterService.classify_query("Compare document A vs document B")
    assert info["query_type"] == "comparison"
