from llama_cloud import AsyncLlamaCloud
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document as LangchainDocument
from src.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams
import os

# Initialize LlamaCloud
client = AsyncLlamaCloud(token=settings.llama_cloud_api_key)

# Initialize Qdrant Client
qdrant_client = QdrantClient(
    url=settings.qdrant_url, 
    api_key=settings.qdrant_api_key
)

# Ensure collection exists with both dense and sparse vector configurations
try:
    qdrant_client.get_collection(collection_name=settings.qdrant_collection_name)
except Exception:
    qdrant_client.create_collection(
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

dense_embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small", 
    api_key=settings.openai_api_key
)

sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=settings.qdrant_collection_name,
    embedding=dense_embeddings,
    sparse_embedding=sparse_embeddings,
    retrieval_mode=RetrievalMode.HYBRID,
    vector_name="dense",
    sparse_vector_name="sparse"
)

async def process_and_index_document(file_path: str, user_id: str, conversation_id: str):
    """
    Parses a document using LlamaParse and indexes it into Qdrant with metadata.
    """
    # Upload and Parse with LlamaCloud
    with open(file_path, "rb") as f:
        file_obj = await client.files.upload_file(file=f)
        
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
        await vector_store.aadd_documents(langchain_docs)
    
    return len(langchain_docs)

def get_retriever(user_id: str, conversation_id: str = None):
    """
    Returns a retriever scoped to the specific user and conversation.
    """
    filter_dict = {"user_id": str(user_id)}
    if conversation_id:
        filter_dict["conversation_id"] = str(conversation_id)
        
    return vector_store.as_retriever(
        search_kwargs={
            "filter": filter_dict,
            "k": 15  # Fetches more context across potentially multiple docs in this conversation
        }
    )
