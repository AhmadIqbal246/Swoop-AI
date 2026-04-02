import json
import cohere
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from app.services.vector_db import get_vector_store
from app.core.config import get_settings

settings = get_settings()

# Initialize Cohere Client (Smarter, Enterprise-grade Reranking)
co = cohere.Client(api_key=settings.COHERE_API_KEY)

# GLOBAL INITIALIZATION (Preloading) to eliminate 3s Cold Start
# This ensures Vector Search and the LLM are ready BEFORE the first request arrives.
print("Engine Warming Up: Preloading Vector Store & LLM...")
vectorstore = get_vector_store()
llm = ChatGroq(
    model_name=settings.LLM_MODEL,
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.1
)

from typing import Optional

def format_docs(docs):
    """Utility to join document contents into a single string for the prompt."""
    return "\n\n".join(doc.page_content for doc in docs)

def neural_rerank(inputs: dict) -> list:
    """
    Uses Cohere's world-class Rerank API to select the absolute best context.
    Returns a list of (document_object, relevance_score) tuples.
    """
    query = inputs["question"]
    docs = inputs["context"]
    
    if not docs:
        return []

    # Map docs to text snippets for Cohere
    texts = [doc.page_content for doc in docs]
    
    # Call Cohere Rerank API (v3.5 is the latest and most accurate)
    rerank_results = co.rerank(
        query=query, 
        documents=texts, 
        top_n=5, 
        model='rerank-v3.5'
    )
    
    # Return document objects paired with their neural relevancy scores
    return [(docs[res.index], res.relevance_score) for res in rerank_results.results]

async def stream_answer(query: str, context_url: Optional[str] = None):
    """
    Asynchronous generator that streams LLM tokens to the client in real-time.
    Uses Precision Filtering to only show highly relevant sources.
    """
    # Use global preloaded retriever
    search_kwargs = {"k": 20, "fetch_k": 40}
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs=search_kwargs
    )
    
    prompt = ChatPromptTemplate.from_template("""
    You are Swoop AI, a highly intelligent, polite technical assistant. 
    You have access to a vast Global Knowledge Base of multiple websites.

    STRICT RULES:
    1. GREETINGS: If the user simply says hello, hi, thanks, or asks how you are, respond politely as an AI assistant.
    2. FACTUAL BASIS: Base your answer EXCLUSIVELY on the provided context below.
    3. MISSING DATA: If the user's question cannot be answered using the provided context, you MUST respond with: 
       "I'm sorry, but I don't have enough information in my database to answer that question accurately. Is there anything else you'd like to know?"
    4. DO NOT invent, guess, or use outside knowledge.

    Context: {context}
    
    Question: {question}
    
    Answer:""")

    # 1. Retrieval and Cohere Reranking
    raw_docs = retriever.invoke(query)
    scored_docs = neural_rerank({"question": query, "context": raw_docs})
    
    # We take all docs for the AI context to ensure it has full perspective
    top_docs = [doc for doc, score in scored_docs]
    context_text = format_docs(top_docs)

    # 2. SOURCE PRECISION FILTERING (The Fix)
    # Only show sources if Cohere is at least 30% sure the doc is actually related
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "nice", "wow", "ok", "okay"]
    
    sources = []
    if not is_greeting:
        # Filter sources based on neural relevance threshold (0.3)
        sources = list(set([
            doc.metadata.get("url") 
            for doc, score in scored_docs 
            if doc.metadata.get("url") and score >= 0.3
        ]))
    
    # 3. Yield metadata first as a JSON chunk
    yield json.dumps({"type": "metadata", "sources": sources}) + "\n"

    # 4. Stream tokens from the preloaded Groq LLM
    chain = prompt | llm | StrOutputParser()
    
    async for chunk in chain.astream({"context": context_text, "question": query}):
        yield json.dumps({"type": "token", "content": chunk}) + "\n"

def generate_answer(query: str, context_url: Optional[str] = None):
    """
    Normal synchronous version with Precision Filtering.
    """
    search_kwargs = {"k": 20, "fetch_k": 40}
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs=search_kwargs
    )
    
    prompt = ChatPromptTemplate.from_template("""
    You are Swoop AI, a highly intelligent, polite technical assistant. 
    You have access to a vast Global Knowledge Base of multiple websites.

    STRICT RULES:
    1. GREETINGS: If the user simply says hello, hi, thanks, or asks how you are, respond politely as an AI assistant.
    2. FACTUAL BASIS: Base your answer EXCLUSIVELY on the provided context below.
    3. MISSING DATA: If the user's question cannot be answered using the provided context, you MUST respond with: 
       "I'm sorry, but I don't have enough information in my database to answer that question accurately. Is there anything else you'd like to know?"
    4. DO NOT invent, guess, or use outside knowledge.

    Context: {context}
    
    Question: {question}
    
    Answer:""")
    
    raw_docs = retriever.invoke(query)
    scored_docs = neural_rerank({"question": query, "context": raw_docs})
    top_docs = [doc for doc, score in scored_docs]
    
    # Reuse preloaded llm
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": format_docs(top_docs), "question": query})
    
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "nice", "wow", "ok", "okay"]
    
    sources = []
    if not is_greeting:
        sources = list(set([
            doc.metadata.get("url") 
            for doc, score in scored_docs 
            if doc.metadata.get("url") and score >= 0.3
        ]))

    return {"answer": answer, "sources": sources}




