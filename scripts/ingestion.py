"""
ingestion.py

Document ingestion pipeline:
  1. Download/load file from URL or path
  2. Parse with LlamaParse (handles PDF, DOCX, PPTX, etc.)
  3. Chunk text with LangChain splitter
  4. Generate hybrid embeddings (dense + sparse)
  5. Upsert into Qdrant (create collection if it doesn't exist)

Called by the POST /api/v1/ingest endpoint.
"""
import os
import tempfile
from pathlib import Path

import httpx
from llama_parse import LlamaParse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse


from app.config import get_settings

settings = get_settings()


# --- Qdrant collection setup -------------------------------------------




# --- Step 1: Download file from URL ------------------------------------

async def download_file(url: str) -> Path:
    """Download a remote file to a temp path. Returns the local path."""
    suffix = Path(url.split("?")[0]).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()
        tmp.write(response.content)
    tmp.close()
    return Path(tmp.name)


# --- Step 2: Parse with LlamaParse ------------------------------------

def parse_document(file_path: Path) -> list[str]:
    """
    Use LlamaParse to extract clean text from any supported document.
    Returns a list of page-level text strings.
    """
    parser = LlamaParse(
        api_key=settings.llama_cloud_api_key,
        result_type="markdown",   # Rich markdown output, great for chunking
        verbose=False,
    )
    documents = parser.load_data(str(file_path))
    return [doc.text for doc in documents if doc.text.strip()]


# --- Step 3: Chunk text -----------------------------------------------

def chunk_texts(pages: list[str], source: str) -> list[Document]:
    """
    Split page texts into overlapping chunks.
    Each chunk becomes a LangChain Document with source metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    all_docs = []
    for page_num, text in enumerate(pages):
        chunks = splitter.split_text(text)
        for chunk in chunks:
            all_docs.append(Document(
                page_content=chunk,
                metadata={"source": source, "page": page_num + 1},
            ))
    return all_docs


# --- Step 4 + 5: Embed and upsert to Qdrant --------------------------

def store_documents(docs: list[Document], collection_name: str) -> int:
    """
    Generate hybrid embeddings and upsert into Qdrant.
    Returns the number of documents stored.
    """
    QdrantVectorStore.from_documents(
        documents=docs,
        embedding=OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key,
        ),
        sparse_embedding=FastEmbedSparse(model_name="Qdrant/bm25"),
        collection_name=collection_name,
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
        force_recreate=False,   # Never wipe existing data
    )
    return len(docs)


# --- Main pipeline entrypoint -----------------------------------------

async def ingest_document(source_url: str, collection_name: str | None = None) -> int:
    """
    Full pipeline: download → parse → chunk → embed → store.
    Returns the number of chunks stored.
    """
    target_collection = collection_name or settings.qdrant_collection_name


    # Download file
    is_remote = source_url.startswith("http://") or source_url.startswith("https://")
    if is_remote:
        file_path = await download_file(source_url)
        cleanup = True
    else:
        file_path = Path(source_url)
        cleanup = False

    try:
        # Parse
        print(f"[ingestion] Parsing: {file_path.name}")
        pages = parse_document(file_path)
        if not pages:
            raise ValueError("LlamaParse returned no text from the document.")

        # Chunk
        docs = chunk_texts(pages, source=source_url)
        print(f"[ingestion] Created {len(docs)} chunks from {len(pages)} pages.")

        # Store
        count = store_documents(docs, target_collection)
        print(f"[ingestion] Stored {count} chunks in '{target_collection}'.")
        return count

    finally:
        if cleanup and file_path.exists():
            os.unlink(file_path)
