from pinecone import Pinecone
from app.core.config import get_settings
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List, Dict

settings = get_settings()

def get_embeddings():
    """Returns the initialized embedding model."""
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={'token': settings.HUGGINGFACEHUB_API_TOKEN}
    )

def get_vector_store():
    """Connects to Pinecone and returns an initialized vector store."""
    embeddings = get_embeddings()
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    
    vectorstore = PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME, 
        embedding=embeddings,
        pinecone_api_key=settings.PINECONE_API_KEY
    )
    return vectorstore

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
    
    print(f"Successfully upserted {len(chunks)} HIGH-QUALITY STRUCTURAL vectors into Pinecone.")
