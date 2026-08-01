"""
agents/tools/web_search.py

Tavily-powered web search tools — general web + dedicated news.
"""
from langchain_community.tools.tavily_search import TavilySearchResults


tavily_tool = TavilySearchResults(
    max_results=5,
    topic="general",
    search_depth="advanced",
    include_raw_content=True,
)

tavily_news_tool = TavilySearchResults(
    name="tavily_news_search",
    max_results=5,
    topic="news",
    search_depth="advanced",
    include_raw_content=True,
    description=(
        "Search for the latest breaking news, current events, sports results, "
        "live scores, recent announcements, and real-time updates. "
        "Use this instead of general web search when the query is about "
        "recent news, today's events, or anything time-sensitive."
    ),
)
