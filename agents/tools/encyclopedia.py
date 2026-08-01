"""
agents/tools/encyclopedia.py

Wikipedia encyclopedic search tool.
"""
from langchain_core.tools import Tool


def _search_wikipedia(query: str) -> str:
    """Search Wikipedia for broad background, definitions, and history."""
    try:
        import httpx

        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 3,
        }
        resp = httpx.get(url, params=params, timeout=10)
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


wikipedia_tool = Tool(
    name="wikipedia_search",
    func=_search_wikipedia,
    description=(
        "Search Wikipedia. Best for broad background, historical facts, definitions, "
        "biographies, and concepts. Input should be a search query string."
    ),
)
