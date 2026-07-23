from typing import List
import logging
from urllib.parse import urlparse
from ddgs import DDGS
from app.schemas.web_search import SearchResultItemSchema, ContentTypeLiteral

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Search service integrating DuckDuckGo Search (DDGS).
    Refines queries based on content_type (pdf, youtube, audio), ranks results, and returns up to 5 results.
    """

    @staticmethod
    def score_audio_result(item: SearchResultItemSchema) -> float:
        """
        Calculates a deterministic quality score for an Audio Search result item.
        Prioritizes direct analyzable content pages (YouTube watch, SoundCloud tracks, Podcast episodes, Archive.org media)
        over generic homepages, search result pages, or coding documentation.
        """
        score = 0.0
        url = item.url.strip() if item.url else ""
        url_lower = url.lower()
        title_lower = item.title.lower() if item.title else ""
        
        try:
            parsed = urlparse(url_lower)
            path = parsed.path or ""
        except Exception:
            path = ""

        # 1. High-Quality Direct Media Domains & Paths
        if "youtube.com/watch" in url_lower or "youtu.be/" in url_lower:
            score += 50.0
        elif "archive.org/details/" in url_lower:
            score += 45.0
        elif "soundcloud.com/" in url_lower and len(path.strip("/").split("/")) >= 2:
            score += 40.0
        elif "spotify.com/episode" in url_lower or "spotify.com/track" in url_lower:
            score += 40.0
        elif "podcasts.apple.com" in url_lower:
            score += 40.0
        elif "librivox.org" in url_lower or "audible.com/pd/" in url_lower:
            score += 45.0
        elif "ted.com/talks" in url_lower:
            score += 45.0
        elif "npr.org" in url_lower and ("episode" in path or "player" in path or "20" in path):
            score += 40.0

        # 2. Media Keywords Signals in URL & Title
        media_url_signals = [".mp3", ".wav", ".m4a", ".ogg", "podcast", "episode", "lecture", "speech", "track", "audio", "chapter"]
        if any(sig in url_lower for sig in media_url_signals):
            score += 15.0

        media_title_signals = ["official audio", "full episode", "podcast", "audiobook", "speech", "lecture", "track", "listen", "full album"]
        if any(sig in title_lower for sig in media_title_signals):
            score += 15.0

        # 3. Path Specificity Bonus (Direct content pages vs Root homepages)
        path_segments = [s for s in path.strip("/").split("/") if s]
        if len(path_segments) >= 2:
            score += 15.0
        elif len(path_segments) == 1:
            score += 5.0
        else:
            score -= 30.0

        # 4. Low-Quality & Irrelevant Page Penalties
        if any(noise in url_lower for noise in ["roblox.com", "w3schools.com", "developer.mozilla.org", "html5", "audio_tag", "js_audio"]):
            score -= 60.0

        if any(nav in url_lower for nav in ["/category/", "/tags/", "/search", "/browse", "/catalog", "docs", "documentation", "wiki"]):
            score -= 35.0

        if any(nav in title_lower for nav in ["home", "welcome", "index of", "search results", "category", "documentation"]):
            score -= 25.0

        return score

    @staticmethod
    def rank_audio_results(results: List[SearchResultItemSchema]) -> List[SearchResultItemSchema]:
        """
        Sorts audio search results by calculated quality score in descending order.
        """
        if not results:
            return []
        
        scored_results = [
            (WebSearchService.score_audio_result(item), item)
            for item in results
        ]
        
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_results]

    @staticmethod
    def refine_audio_query(query: str) -> str:
        """
        Intelligently refines Audio Search queries using deterministic keyword heuristics.
        Classifies query intent into categories: Song, Podcast, Audiobook, Speech/Interview, Lecture/Course, or Generic Audio.
        """
        q_clean = query.strip()
        q_lower = q_clean.lower()
        words = set(q_lower.split())

        # If user already specified explicit intent keyword in query, preserve query
        if any(keyword in q_lower for keyword in ["podcast", "audiobook", "lecture", "speech", "interview", "official audio"]):
            return q_clean

        # Category 1: Speech / Interview
        speech_keywords = {"speech", "commencement", "address", "remarks", "keynote", "interview", "statement", "jobs"}
        if words.intersection(speech_keywords) or "steve jobs" in q_lower:
            return f"{q_clean} speech"

        # Category 2: Podcast
        podcast_keywords = {
            "podcast", "huberman", "rogan", "lex", "fridman", "ferriss", "episode", "ep",
            "show", "broadcast", "daily", "npr", "ted"
        }
        if words.intersection(podcast_keywords) or any(name in q_lower for name in ["huberman", "rogan", "lex fridman"]):
            return f"{q_clean} podcast"

        # Category 3: Audiobook
        audiobook_keywords = {
            "audiobook", "book", "habits", "atomic", "novel", "author", "chapter",
            "biography", "memoir", "edition", "summary"
        }
        if words.intersection(audiobook_keywords):
            return f"{q_clean} audiobook"

        # Category 4: Lecture / Course
        lecture_keywords = {
            "mit", "stanford", "harvard", "oxford", "cambridge", "berkeley",
            "lecture", "course", "class", "systems", "physics", "math",
            "chemistry", "biology", "history", "computer", "science", "professor",
            "101", "cs50", "tutorial", "lesson"
        }
        if words.intersection(lecture_keywords) or any(uni in q_lower for uni in ["mit", "stanford", "harvard", "berkeley", "oxford"]):
            return f"{q_clean} lecture"

        # Category 5: Song
        song_keywords = {
            "song", "lyrics", "track", "album", "feat", "ft", "single", "remix",
            "acoustic", "music", "wanna", "love", "heart", "dance", "band", "artist"
        }
        if words.intersection(song_keywords) or "wanna" in words or "lyrics" in words:
            return f"{q_clean} official audio OR lyrics OR youtube"

        # Category 6: Ambient / Sound / Generic Audio
        ambient_keywords = {
            "rain", "sleep", "relaxing", "thunder", "asmr", "waves", "noise",
            "meditation", "ambient", "calm", "nature", "sound", "sounds"
        }
        if words.intersection(ambient_keywords):
            return f"{q_clean} audio"

        # Default generic audio query refinement
        return f"{q_clean} audio"

    @staticmethod
    async def search(query: str, content_type: ContentTypeLiteral) -> List[SearchResultItemSchema]:
        # Refine internal search query based on content_type
        if content_type == "pdf":
            refined_query = f"{query} filetype:pdf"
        elif content_type == "youtube":
            refined_query = f"{query} site:youtube.com"
        elif content_type == "audio":
            refined_query = WebSearchService.refine_audio_query(query)
        else:
            refined_query = query

        results: List[SearchResultItemSchema] = []

        try:
            ddgs = DDGS()
            search_results = list(ddgs.text(refined_query, max_results=5))
            if not search_results and refined_query != query:
                search_results = list(ddgs.text(query, max_results=5))

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

        if content_type == "audio" and results:
            results = WebSearchService.rank_audio_results(results)

        return results
