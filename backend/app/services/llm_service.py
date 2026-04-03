import json
import os
import re
import cohere
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from app.services.vector_db import get_vector_store
from app.core.config import get_settings
from app.services.history_service import HistoryManager

settings = get_settings()

# Initialize Cohere Client (Smarter, Enterprise-grade Reranking)
co = cohere.Client(api_key=settings.COHERE_API_KEY)

# GLOBAL INITIALIZATION (Preloading) 🚀
# This ensures the LLM is ready BEFORE the first request arrives.
print("Engine Warming Up: Preloading LLM & Embeddings...")
llm = ChatGroq(
    model_name=settings.LLM_MODEL,
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.0,
    streaming=True
)

def format_docs(docs: List[Any]) -> str:
    """Utility to join document contents into a single string for the prompt."""
    return "\n\n".join(doc.page_content for doc in docs)

async def neural_rerank_async(query: str, docs: List[Any]) -> List[Tuple[Any, float]]:
    """
    Asynchronous wrapper for Cohere's Rerank API to select the absolute best context.
    Returns a list of (document_object, relevance_score) tuples.
    """
    if not docs:
        return []

    texts = [doc.page_content for doc in docs]
    
    try:
        # We run this in a thread to keep the event loop moving during the API call
        rerank_results = await asyncio.to_thread(
            co.rerank,
            query=query, 
            documents=texts, 
            top_n=10, 
            model='rerank-v3.5'
        )
        return [(docs[res.index], res.relevance_score) for res in rerank_results.results]
    except Exception as e:
        print(f"⚠️ Cohere Rerank Timeout/Error: {e}. Falling back to standard retrieval.")
        return [(doc, 1.0) for doc in docs[:9]]

def get_base_url_filter(url: str) -> Optional[Dict[str, Any]]:
    """Utility: Robust URL filter logic (Catches URL with AND without trailing slashes!)"""
    if not url: return None
    clean = url.rstrip('/')
    return {"base_url": {"$in": [clean, clean + '/']}}

async def condense_query(query: str, history_str: str) -> str:
    """
    ELITE CONDENSER:
    Transforms a dialogue-dependent question into a standalone search query.
    If no history, returns original query cleaned.
    """
    if not history_str:
        return re.sub(r'https?://[^\s,]+', '', query).strip() or "Tell me about this website"

    condense_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Query Architect. Given a conversation history and a new question, output ONLY a standalone search query that captures the core intent. Do NOT answer the question. Just output the search text."),
        ("human", f"Chat History:\n{history_str}\n\nNew Question: {query}")
    ])
    
    chain = condense_prompt | llm | StrOutputParser()
    standalone = await chain.ainvoke({})
    return standalone.strip()

async def retrieve_context(query: str, context_url: Optional[str] = None, history_str: str = "") -> Tuple[str, List[str]]:
    """
    CORE RETRIEVAL ENGINE 🧠⚡
    Performs high-performance Hybrid Search, Deduplication, and Neural Reranking.
    Returns: (context_text, list_of_source_urls)
    """
    vectorstore = get_vector_store()
    
    # 1. SMART CONDENSATION (Context-Aware Search) 🧠
    search_query = await condense_query(query, history_str)
    print(f"🔍 Optimized Search Query: {search_query}")

    # 2. PARALLEL TRIPLE-THREAT SEARCH 🕵️‍♂️🎯
    search_tasks = []
    
    # A. Global Semantic Search (The Broad Net)
    search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=30))

    # B. Targeted Domain Search (The Precision Strike)
    if context_url:
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=40, filter=get_base_url_filter(context_url)))

    # C. Factual Expansion (The Extra Mile)
    contact_keywords = ["contact", "email", "phone", "location", "address", "call", "reach", "pricing", "cost", "plans"]
    if any(word in search_query.lower() for word in contact_keywords):
        factual_query = "contact details email phone address pricing plans cost structure"
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, factual_query, k=20))

    # EXECUTE SEARCHES IN PARALLEL 🚀
    search_results = await asyncio.gather(*search_tasks)
    
    # 3. DEDUPLICATION
    raw_docs = [doc for result in search_results for doc in result]
    unique_docs = []
    seen_contents = set()
    for doc in raw_docs:
        # Simple dedupe by content
        if doc.page_content not in seen_contents:
            unique_docs.append(doc)
            seen_contents.add(doc.page_content)

    # 4. NEURAL RERANKING & THRESHOLDING 📉
    # We send the optimized query to Cohere for maximum accuracy
    scored_docs = await neural_rerank_async(search_query, unique_docs)
    
    top_docs = []
    for doc, score in scored_docs:
        if score >= 0.25: # Lowered threshold slightly to catch more context for reranker
            top_docs.append(doc)
        if len(top_docs) >= 12: 
            break

    # Final Fallback
    if not top_docs and unique_docs:
        top_docs = unique_docs[:3]

    context_text = format_docs(top_docs)
    sources = list(set([doc.metadata.get("url") for doc in top_docs]))
    
    return context_text, sources

async def stream_answer(query: str, session_id: str, context_url: Optional[str] = None):
    """
    Asynchronous generator that streams LLM tokens to the client in real-time.
    Now 100% History-Aware and Context-Precision Optimized.
    """
    # 1. LOAD MEMORY 🧠
    history_str = HistoryManager.get_history_as_string(session_id)
    profile = HistoryManager.get_profile(session_id)
    user_name = profile.get("name", "User")

    yield json.dumps({"type": "status", "content": "🔍 Analyzing conversation history..."}) + "\n"
    
    # 2. FETCH CORE CONTEXT 🧠⚡ (Unified Retrieval Logic)
    context_text, sources = await retrieve_context(query, context_url, history_str)
    
    # 3. FETCH GLOBAL ENTITY INVENTORY (Source of Truth) 🗃️
    inventory_list = []
    try:
        cur_dir = os.path.dirname(os.path.abspath(__file__)) 
        backend_dir = os.path.dirname(os.path.dirname(cur_dir))
        reg_path = os.path.join(backend_dir, "scraped_data", "entities_registry.json")
        
        if os.path.exists(reg_path):
            with open(reg_path, "r", encoding="utf-8") as rf:
                reg_data = json.load(rf)
                inventory_list = sorted(list(reg_data.keys()))
    except Exception as e:
        print(f" Registry Error: {e}")
    
    total_entities = len(inventory_list)
    inventory_str = ", ".join(inventory_list) if inventory_list else "None (System Warmup)"
    
    yield json.dumps({"type": "status", "content": "✨ Synthesizing intelligence..."}) + "\n"

    # 4. THE GOLDEN RULE PROMPT 🏛️🎯 (Updated with History)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are Swoop AI, an elite Intelligence Engine. 

CURRENT SESSION PROFILE:
- USER NAME: {user_name}
- TOTAL ENTITIES INDEXED: {total_entities}
- FULL DOMAIN LIST: [{inventory_str}]

CRITICAL INSTRUCTIONS:
1. KB META-QUERIES: If the user asks about your database, use the STATS above.
2. ZERO HALLUCINATION: Build answers EXCLUSIVELY on the <knowledge_base>. 
3. HISTORY AWARENESS: Use the <chat_history> to maintain dialogue flow. If the user refers to "it" or "the company," check the history.
4. NAME USAGE: If a USER NAME is provided and not generic, acknowledge it naturally once.
5. DECLINE GRACEFULLY: If info is missing, say so politely. Do NOT guess.
6. NO INTRO FLUFF: The first sentence must start with the direct answer or main subject.

PROPORTIONAL DEPTH:
- Greetings: Warm but professional.
- Specific Questions: Short and direct.
- Overviews: Structured Markdown with headers.
"""),
        ("human", f"""<chat_history>\n{history_str}\n</chat_history>\n\n<knowledge_base>\n{{context}}\n</knowledge_base>\n\nQuestion: {{question}}""")
    ])

    # 5. STREAM TOKENS 🌊
    chain = prompt | llm | StrOutputParser()
    full_response = ""
    async for chunk in chain.astream({"context": context_text, "question": query}):
        full_response += chunk
        yield json.dumps({"type": "token", "content": chunk}) + "\n"

    # 6. SAVE TO MEMORY 💾
    HistoryManager.add_message(session_id, "user", query)
    HistoryManager.add_message(session_id, "assistant", full_response)
    
    # Extra: Detect if user shared their name (Basic Identity Extraction)
    if "my name is " in query.lower():
        extracted_name = query.lower().split("my name is ")[1].title().split()[0].replace(".", "").replace("!", "")
        HistoryManager.store_fact(session_id, "name", extracted_name)

    # 7. CONDITIONAL SOURCE DISPLAY
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "ok", "okay"]
    meta_keywords = ["how many", "which companies", "what companies", "total", "inventory"]
    is_meta = any(word in query.lower() for word in meta_keywords)
    
    final_sources = []
    if not is_greeting and not is_meta and "don't have enough specific information" not in full_response.lower():
        final_sources = sources

    yield json.dumps({"type": "metadata", "sources": final_sources}) + "\n"
