import time
from pinecone import Pinecone
from app.core.config import get_settings
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List, Dict
from app.core.logging import app_logger as logger # Fix 1.2: Standardized Logging

settings = get_settings()

# INITIALIZE MODELS ON BOOT (Eliminates the 10-20s First-Query Lag) 🚀
start_time = time.perf_counter()
logger.info("Engine: Performing Deep Warmup (Embeddings & Index)...")
_embeddings = HuggingFaceEmbeddings(
    model_name=settings.EMBEDDING_MODEL,
    model_kwargs={'token': settings.HUGGINGFACEHUB_API_TOKEN}
)

_vector_store = PineconeVectorStore(
    index_name=settings.PINECONE_INDEX_NAME, 
    embedding=_embeddings,
    pinecone_api_key=settings.PINECONE_API_KEY
)
logger.info("Engine: Warmup Complete. Ready for Instant Search.", extra={"duration": time.perf_counter() - start_time})

def get_embeddings():
    """Returns the pre-initialized global embedding model."""
    return _embeddings

def get_vector_store():
    """Returns the pre-initialized global vector store instance."""
    return _vector_store

def upsert_structural_chunks(chunks: List[Dict[str, any]]):
    """
    NEW: Upserts structurally-aware chunks with rich metadata.
    Each chunk in the list is a dictionary: {'content': str, 'metadata': dict}
    """
    vectorstore = get_vector_store()
    
    texts = [c["content"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    
    # Add to index (Pinecone handles vectors, we provide text + metadata)
    vectorstore.add_texts(texts=texts, metadatas=metadatas)
    
    logger.info("Chunks upserted to Pinecone", extra={"count": len(chunks)}) # Fix 1.2: Traceability
