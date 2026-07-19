from typing import List
import logging
from ddgs import DDGS
from app.schemas.web_search import SearchResultItemSchema, ContentTypeLiteral

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Search service integrating DuckDuckGo Search (DDGS).
    Refines queries based on content_type (pdf, youtube, audio) and returns up to 5 results.
    """

    @staticmethod
    async def search(query: str, content_type: ContentTypeLiteral) -> List[SearchResultItemSchema]:
        # Refine internal search query based on content_type
        if content_type == "pdf":
            refined_query = f"{query} filetype:pdf"
        elif content_type == "youtube":
            refined_query = f"{query} site:youtube.com"
        elif content_type == "audio":
            refined_query = f"{query} podcast OR audio"
        else:
            refined_query = query

        results: List[SearchResultItemSchema] = []

        try:
            ddgs = DDGS()
            search_results = list(ddgs.text(refined_query, max_results=5))

            for item in search_results:
                title = item.get("title", "").strip() or "Untitled Result"
                url = item.get("href") or item.get("link") or item.get("url") or ""

                if url:
                    results.append(
                        SearchResultItemSchema(
                            title=title,
                            url=url,
                            type=content_type
                        )
                    )
        except Exception as err:
            logger.error(f"DDGS web search error for query '{refined_query}': {err}")
            # On error return empty results list without crashing
            return []

        return results
