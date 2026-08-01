"""
agents/tools/academic.py

Academic research tools — Arxiv and PubMed.
"""
from langchain_core.tools import Tool


def _search_arxiv(query: str) -> str:
    """Search arXiv academic papers safely across different SDK versions."""
    try:
        import arxiv

        if hasattr(arxiv, "Client"):
            client = arxiv.Client()
            search = arxiv.Search(query=query, max_results=3, sort_by=arxiv.SortCriterion.Relevance)
            results = list(client.results(search))
        else:
            search = arxiv.Search(query=query, max_results=3)
            results = list(search.results())

        if not results:
            return "No relevant arXiv papers found for this query."

        formatted = []
        for r in results:
            summary = r.summary.replace("\n", " ")[:1000]
            formatted.append(
                f"Title: {r.title}\n"
                f"Authors: {', '.join(a.name for a in r.authors)}\n"
                f"URL: {r.entry_id}\n"
                f"Summary: {summary}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"arXiv search failed: {str(e)}"


arxiv_tool = Tool(
    name="arxiv_search",
    func=_search_arxiv,
    description=(
        "Search academic papers on arXiv. Use for computer science, physics, mathematics, "
        "AI, and technical engineering papers. Input should be a concise query string."
    ),
)


def _search_pubmed(query: str) -> str:
    """Search PubMed NCBI database for medical, biological, and life science papers."""
    try:
        import httpx

        esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 3}
        resp = httpx.get(esearch_url, params=params, timeout=10)
        id_list = resp.json().get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return "No PubMed medical articles found for this query."

        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
        sum_resp = httpx.get(esummary_url, params=summary_params, timeout=10)
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


pubmed_tool = Tool(
    name="pubmed_search",
    func=_search_pubmed,
    description=(
        "Search PubMed (NCBI). Best for medical, clinical, pharmaceutical, "
        "biological, and life science research papers. Input should be a search query string."
    ),
)
