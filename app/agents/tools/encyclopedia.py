"""
app/agents/tools/encyclopedia.py

Wikipedia encyclopedic search tool (pure asynchronous implementation).
"""
import httpx
from langchain_core.tools import StructuredTool


async def _search_wikipedia_async(query: str) -> str:
    """Native asynchronous Wikipedia search via httpx.AsyncClient."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = "https://en.wikipedia.org/w/api.php"
            params: dict[str, str | int] = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 3,
            }
            resp = await client.get(url, params=params)
            data = resp.json()
            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                return "No Wikipedia articles found."

            snippets = []
            for item in search_results:
                title = item.get("title")
                snippet = item.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '')
                snippets.append(f"Title: {title}\nSnippet: {snippet}")
            return "\n\n---\n\n".join(snippets)
    except Exception as e:
        return f"Wikipedia search unavailable: {str(e)}"


wikipedia_tool = StructuredTool.from_function(
    coroutine=_search_wikipedia_async,
    name="wikipedia_search",
    description=(
        "Search Wikipedia. Best for broad background, historical facts, definitions, "
        "biographies, and concepts. Input should be a search query string."
    ),
)
