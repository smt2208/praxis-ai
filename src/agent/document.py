from llama_cloud import AsyncLlamaCloud
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document as LangchainDocument
from src.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams
from io import BytesIO
import aiofiles
import os
import logging

logger = logging.getLogger(__name__)

# Initialize LlamaCloud (llama-cloud v2.x uses api_key=, not token=)
client = AsyncLlamaCloud(api_key=settings.llama_cloud_api_key)

# ---------------------------------------------------------------------------
# Lazy Qdrant initialization
# ---------------------------------------------------------------------------
# IMPORTANT: We do NOT connect to Qdrant at module import time.
# Doing so would crash the entire app on startup if Qdrant is temporarily
# unreachable (e.g., the Qdrant EC2 is stopped, Security Group blocks port).
# Instead, we initialize lazily on first actual use.
# ---------------------------------------------------------------------------
_qdrant_client: QdrantClient | None = None
_vector_store: QdrantVectorStore | None = None
_dense_embeddings: OpenAIEmbeddings | None = None
_sparse_embeddings: FastEmbedSparse | None = None


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=10,         # Fail fast — don't hang for 30s
            check_compatibility=False,  # Skip version check to avoid extra call
        )
        # Ensure the collection exists
        try:
            _qdrant_client.get_collection(collection_name=settings.qdrant_collection_name)
            logger.info(f"Qdrant collection '{settings.qdrant_collection_name}' found.")
        except Exception:
            logger.info(f"Creating Qdrant collection '{settings.qdrant_collection_name}'...")
            _qdrant_client.create_collection(
                collection_name=settings.qdrant_collection_name,
                vectors_config={
                    "dense": VectorParams(size=1536, distance=Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams(on_disk=False)
                    )
                }
            )
    return _qdrant_client


def _get_vector_store() -> QdrantVectorStore:
    global _vector_store, _dense_embeddings, _sparse_embeddings
    if _vector_store is None:
        _dense_embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key
        )
        _sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
        _vector_store = QdrantVectorStore(
            client=_get_qdrant_client(),
            collection_name=settings.qdrant_collection_name,
            embedding=_dense_embeddings,
            sparse_embedding=_sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse"
        )
    return _vector_store


async def process_and_index_document(file_path: str, user_id: str, conversation_id: str):
    """
    Parses a document using LlamaParse and indexes it into Qdrant with metadata.
    """
    # Read file asynchronously (non-blocking)
    async with aiofiles.open(file_path, "rb") as f:
        file_bytes = await f.read()

    # Upload to LlamaCloud for parsing
    file_obj = await client.files.upload_file(
        file=(os.path.basename(file_path), BytesIO(file_bytes))
    )

    result = await client.parsing.parse(
        file_id=file_obj.id,
        tier="agentic",
        version="latest",
        expand=["markdown"]
    )

    langchain_docs = []
    if result.markdown and result.markdown.pages:
        for page in result.markdown.pages:
            lc_doc = LangchainDocument(
                page_content=page.markdown,
                metadata={
                    "user_id": str(user_id),
                    "conversation_id": str(conversation_id),
                    "source": os.path.basename(file_path)
                }
            )
            langchain_docs.append(lc_doc)

    if langchain_docs:
        await _get_vector_store().aadd_documents(langchain_docs)

    return len(langchain_docs)


def get_retriever(user_id: str, conversation_id: str = None):
    """
    Returns a retriever scoped to the specific user and conversation.
    """
    filter_dict = {"user_id": str(user_id)}
    if conversation_id:
        filter_dict["conversation_id"] = str(conversation_id)

    return _get_vector_store().as_retriever(
        search_kwargs={
            "filter": filter_dict,
            "k": 15
        }
    )
