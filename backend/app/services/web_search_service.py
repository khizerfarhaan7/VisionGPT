from typing import List
import logging
from urllib.parse import urlparse, parse_qs
from ddgs import DDGS
from app.schemas.web_search import SearchResultItemSchema, ContentTypeLiteral

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Search service integrating DuckDuckGo Search (DDGS).
    Refines queries based on content_type (pdf, youtube) and returns up to 5 results.
    """

    @staticmethod
    def is_importable_youtube_video_url(url: str) -> bool:
        """
        Validates if a URL is an individual, directly importable YouTube video.
        Rejects channel pages, playlist pages, shorts, user profiles, handles,
        community pages, browse/feed pages, and search result pages.
        """
        if not url or not isinstance(url, str):
            return False

        url_clean = url.strip()
        if not url_clean:
            return False

        try:
            parsed = urlparse(url_clean)
        except Exception:
            return False

        if parsed.scheme not in ("http", "https"):
            return False

        hostname = (parsed.hostname or "").lower()
        is_youtube = (
            hostname == "youtu.be"
            or hostname.endswith(".youtu.be")
            or hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
        )
        if not is_youtube:
            return False

        path_lower = (parsed.path or "").lower()

        # Reject explicitly non-video YouTube page types
        rejected_patterns = [
            "/channel",
            "/playlist",
            "/shorts",
            "/user",
            "/@",
            "/community",
            "/browse",
            "/feed",
            "/explore",
            "/trending",
            "/results",
            "/search",
            "/about",
            "/store",
            "/posts",
            "/hashtag",
        ]

        if any(pattern in path_lower for pattern in rejected_patterns):
            return False

        # Validate video specific path / query structures
        if "youtu.be" in hostname:
            path_segments = [s for s in path_lower.strip("/").split("/") if s]
            return len(path_segments) == 1 and bool(path_segments[0])
        else:
            # youtube.com domain
            if path_lower in ("/watch", "/watch/"):
                query_params = parse_qs(parsed.query)
                video_ids = query_params.get("v")
                return bool(video_ids and video_ids[0] and video_ids[0].strip())

            if path_lower.startswith("/v/") or path_lower.startswith("/embed/"):
                path_segments = [s for s in path_lower.strip("/").split("/") if s]
                return len(path_segments) == 2 and bool(path_segments[1])

            return False

    @staticmethod
    async def search(query: str, content_type: ContentTypeLiteral) -> List[SearchResultItemSchema]:
        # Refine internal search query based on content_type
        if content_type == "pdf":
            refined_query = f"{query} filetype:pdf"
        elif content_type == "youtube":
            refined_query = f"{query} site:youtube.com"
        else:
            refined_query = query

        results: List[SearchResultItemSchema] = []

        try:
            ddgs = DDGS()
            fetch_count = 15 if content_type == "youtube" else 5
            search_results = list(ddgs.text(refined_query, max_results=fetch_count))
            if not search_results and refined_query != query:
                search_results = list(ddgs.text(query, max_results=fetch_count))

            for item in search_results:
                title = (item.get("title") or "").strip()
                url = (item.get("href") or item.get("link") or item.get("url") or "").strip()

                if not title or not url:
                    continue

                if content_type == "youtube":
                    if not WebSearchService.is_importable_youtube_video_url(url):
                        continue

                results.append(
                    SearchResultItemSchema(
                        title=title,
                        url=url,
                        type=content_type
                    )
                )

                if len(results) >= 5:
                    break

        except Exception as err:
            logger.error(f"DDGS web search error for query '{refined_query}': {err}")
            # On error return empty results list without crashing
            return []

        return results
