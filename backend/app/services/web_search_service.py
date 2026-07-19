from typing import List
from app.schemas.web_search import SearchResultItemSchema, ContentTypeLiteral

class WebSearchService:
    """
    Search service foundation.
    Currently returns mock data. Will be extended with DuckDuckGo (DDGS) in future prompts.
    """

    @staticmethod
    async def search(query: str, content_type: ContentTypeLiteral) -> List[SearchResultItemSchema]:
        # Return mock JSON results for foundation phase
        mock_results = [
            SearchResultItemSchema(
                title="Machine Learning Fundamentals",
                url="https://example.com/ml.pdf",
                type="pdf"
            ),
            SearchResultItemSchema(
                title="Deep Learning Lecture",
                url="https://youtube.com/example",
                type="youtube"
            ),
            SearchResultItemSchema(
                title="AI Podcast",
                url="https://example.com/audio.mp3",
                type="audio"
            )
        ]
        return mock_results
