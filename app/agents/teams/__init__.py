"""
app/agents/teams — Agent team packages.

Consolidated specialist departments:
  - knowledge: Document RAG & CRAG specialist
  - research:  Deep multi-domain research loop (ArXiv, PubMed, Wikipedia, Web)
  - general:   Fast conversational assistant with real-time web search
  - vision:    Multimodal visual reasoning and document analysis
"""
from app.agents.teams.knowledge import astream_knowledge_team
from app.agents.teams.research import astream_research_team
from app.agents.teams.general import astream_general_agent
from app.agents.teams.vision import astream_vision_agent

__all__ = [
    "astream_knowledge_team",
    "astream_research_team",
    "astream_general_agent",
    "astream_vision_agent",
]
