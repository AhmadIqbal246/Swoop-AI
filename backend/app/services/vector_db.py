import time
from pinecone import Pinecone
from app.core.config import get_settings
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List, Dict, Optional
from app.core.logging import app_logger as logger 
from app.utils.domain_tools import normalize_to_domain

settings = get_settings()

# INITIALIZE MODELS ON BOOT 🚀
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
    return _embeddings

def get_vector_store():
    return _vector_store

def delete_by_domain(domain: str):
    """
    ATOMIC CLEANER 🧹
    Deletes all vectors for a specific domain to prevent duplication.
    """
    try:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(settings.PINECONE_INDEX_NAME)
        
        # We delete by the source_base metadata field
        index.delete(filter={"source_base": {"$eq": domain}})
        logger.info("Atomic Wipe completed", extra={"domain": domain})
    except Exception:
        logger.error("Atomic Wipe failed", exc_info=True, extra={"domain": domain})

def upsert_structural_chunks(chunks: List[Dict[str, any]], source_url: Optional[str] = None):
    """
    UPSERT WITH REFRESH LOGIC 🔄
    Wipes old data for the domain before adding the new version.
    """
    if not chunks:
        return

    # Extract Domain for Atomic Wipe
    if source_url:
        domain = normalize_to_domain(source_url)
        if domain:
            delete_by_domain(domain)
            # Inject source_base into metadata for all chunks if not already there
            for chunk in chunks:
                chunk["metadata"]["source_base"] = domain

    vectorstore = get_vector_store()
    texts = [c["content"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    
    vectorstore.add_texts(texts=texts, metadatas=metadatas)
    logger.info("Chunks upserted to Pinecone", extra={"count": len(chunks), "domain": domain if source_url else "unknown"})
