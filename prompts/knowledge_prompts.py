WEB_EXPERT_PROMPT = """Original question: {query}

We already found this in internal docs:
{rag_results}

Search the web to add any missing context, latest updates, or verify facts. Be concise."""

SYNTHESIZER_SYSTEM = """You are a precise AI assistant. Synthesize the two sources below into a single, coherent answer. Prefer internal doc facts; use web data for freshness. Do not repeat yourself. Be concise."""

SYNTHESIZER_HUMAN = """Question: {query}

Internal Knowledge Base:
{rag_results}

Web Research:
{web_results}"""
