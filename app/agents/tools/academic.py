"""
app/agents/tools/academic.py

Academic research tools:
  - ArXiv: Official LangChain Community ArxivQueryRun.
  - PubMed: High-performance native asynchronous NCBI E-Utilities search via httpx.AsyncClient.
"""
import httpx
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_core.tools import StructuredTool

# ---------------------------------------------------------------------------
# ArXiv Tool (LangChain Official Community Integration)
# ---------------------------------------------------------------------------

arxiv_tool = ArxivQueryRun(
    name="arxiv_search",
    description=(
        "Search academic papers on arXiv. Use for computer science, physics, mathematics, "
        "AI, and technical engineering papers. Input should be a concise query string."
    ),
    api_wrapper=ArxivAPIWrapper(
        top_k_results=3,
        doc_content_chars_max=1500,
    ),
)

# ---------------------------------------------------------------------------
# PubMed Tool (Native Non-Blocking Async NCBI Search)
# ---------------------------------------------------------------------------

async def _search_pubmed_async(query: str) -> str:
    """Native asynchronous PubMed NCBI search via httpx.AsyncClient."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params: dict[str, str | int] = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 3}
            resp = await client.get(esearch_url, params=params)
            id_list = resp.json().get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return "No PubMed medical articles found for this query."

            esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            summary_params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
            sum_resp = await client.get(esummary_url, params=summary_params)
            sum_data = sum_resp.json().get("result", {})

            results = []
            for pmid in id_list:
                item = sum_data.get(pmid, {})
                title = item.get("title", "No title")
                pubdate = item.get("pubdate", "")
                authors = ", ".join(a.get("name", "") for a in item.get("authors", [])[:3])
                results.append(f"Title: {title}\nPMID: {pmid}\nDate: {pubdate}\nAuthors: {authors}")
            return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"PubMed search failed: {str(e)}"


pubmed_tool = StructuredTool.from_function(
    coroutine=_search_pubmed_async,
    name="pubmed_search",
    description=(
        "Search PubMed (NCBI). Best for medical, clinical, pharmaceutical, "
        "biological, and life science research papers. Input should be a search query string."
    ),
)
