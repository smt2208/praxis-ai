"""
app/services/ingestion.py

Document ingestion pipeline:
  1. Download/load file from URL or path
  2. Parse document — smart two-path strategy:
       a. Fast local extraction (PyMuPDF / python-docx) — milliseconds, zero cost
       b. LlamaParse cloud API with fast_mode=True — only when local fails
  3. Chunk text with LangChain splitter
  4. Generate hybrid embeddings (dense + sparse)
  5. Upsert into Qdrant

Called by the POST /api/v1/ingest endpoint.
"""
import os
import logging
import tempfile
import asyncio
from pathlib import Path

import httpx
from langsmith import traceable
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


# --- Step 1: Download file from URL ------------------------------------

async def download_file(url: str) -> Path:
    """Download a remote file to a temp path. Returns the local path."""
    suffix = Path(url.split("?")[0]).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type.startswith("text/html") or content_type.startswith("application/xhtml+xml"):
                raise ValueError(f"Unsupported content type: {content_type}")

            downloaded = 0
            async for chunk in response.aiter_bytes():
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Remote file is too large to ingest safely.")
                tmp.write(chunk)
    tmp.close()
    return Path(tmp.name)


# --- Step 2a: Fast local extraction (no API call) ----------------------

def _try_fast_local_extract(file_path: Path) -> list[str] | None:
    """
    Attempt zero-latency local text extraction for supported formats.
    Returns a list of page-level strings, or None if local extraction is
    not possible (e.g. scanned PDF with no embedded text, PPTX, etc.).
    """
    ext = file_path.suffix.lower()

    if ext in (".txt", ".md"):
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return [text] if text.strip() else None

    if ext == ".pdf":
        try:
            import pymupdf
            doc = pymupdf.open(str(file_path))
            pages = []
            total_pages = doc.page_count
            for page in doc:
                text = page.get_text()
                if text.strip():
                    pages.append(text)
            doc.close()
            if pages and (total_pages == 0 or len(pages) / total_pages >= 0.6):
                return pages
        except ImportError:
            pass
        except Exception:
            pass

    if ext == ".docx":
        try:
            from docx import Document as DocxDocument
            docx = DocxDocument(str(file_path))
            full_text = "\n".join(p.text for p in docx.paragraphs if p.text.strip())
            return [full_text] if full_text.strip() else None
        except ImportError:
            pass
        except Exception:
            pass

    return None


# --- Step 2b: LlamaParse cloud extraction (fallback) -------------------

def _llamaparse_extract(file_path: Path) -> list[str]:
    """Use LlamaParse with fast_mode=True to extract text from complex docs."""
    from llama_parse import LlamaParse
    parser = LlamaParse(
        api_key=settings.llama_cloud_api_key,
        result_type="markdown",
        fast_mode=True,
        verbose=False,
        num_workers=4,
    )
    documents = parser.load_data(str(file_path))
    return [doc.text for doc in documents if doc.text.strip()]


# --- Step 2: Unified parse dispatcher ----------------------------------

@traceable(name="Parse Document", run_type="parser")
def parse_document(file_path: Path) -> list[str]:
    """
    Smart two-path parser:
      1. Try fast local extraction first (milliseconds, no API cost).
      2. Fall back to LlamaParse (seconds) only when local extraction fails.
    """
    pages = _try_fast_local_extract(file_path)
    if pages:
        logger.info("[ingestion] Fast local extraction succeeded (%d pages).", len(pages))
        return pages

    logger.info("[ingestion] Local extraction insufficient — falling back to LlamaParse (fast_mode).")
    return _llamaparse_extract(file_path)


# --- Step 3: Chunk text -----------------------------------------------

@traceable(name="Chunk Texts", run_type="chain")
def chunk_texts(pages: list[str], source: str, user_id: str, conversation_id: str) -> list[Document]:
    """Split page texts into overlapping chunks with per-conversation metadata."""
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
                metadata={"source": source, "page": page_num + 1, "user_id": user_id, "conversation_id": conversation_id},
            ))
    return all_docs


# --- Step 4 + 5: Embed and upsert to Qdrant --------------------------

@traceable(name="Store Vector Documents", run_type="retriever")
def store_documents(docs: list[Document], collection_name: str) -> int:
    """Generate hybrid embeddings and upsert into Qdrant. Returns count stored."""
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
        force_recreate=False,
    )
    return len(docs)


# --- Main pipeline entrypoint -----------------------------------------

@traceable(name="Ingest Document Pipeline", run_type="chain")
async def ingest_document(source_url: str, user_id: str, conversation_id: str) -> int:
    """
    Full pipeline: download → parse → chunk → embed → store.
    Every chunk is tagged with user_id and conversation_id for per-conversation isolation.
    Returns the number of chunks stored.
    """
    target_collection = settings.qdrant_collection_name

    is_remote = source_url.startswith("http://") or source_url.startswith("https://")
    if is_remote:
        file_path = await download_file(source_url)
        cleanup = True
    else:
        file_path = Path(source_url)
        if not file_path.exists():
            raise FileNotFoundError(f"Local file not found: {source_url}")
        cleanup = False

    try:
        logger.info("[ingestion] Parsing: %s", file_path.name)
        pages = await asyncio.to_thread(parse_document, file_path)
        if not pages:
            raise ValueError("Parser returned no text from the document.")

        docs = await asyncio.to_thread(
            chunk_texts, pages, source_url, user_id, conversation_id
        )
        logger.info("[ingestion] Created %d chunks from %d pages.", len(docs), len(pages))

        count = await asyncio.to_thread(store_documents, docs, target_collection)
        logger.info("[ingestion] Stored %d chunks in '%s' for user '%s'.", count, target_collection, user_id)
        return count

    finally:
        if cleanup and file_path.exists():
            os.unlink(file_path)
