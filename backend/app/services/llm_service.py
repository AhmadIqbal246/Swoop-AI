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

async def retrieve_context(query: str, context_url: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    CORE RETRIEVAL ENGINE 🧠⚡
    Performs high-performance Hybrid Search, Deduplication, and Neural Reranking.
    Returns: (context_text, list_of_source_urls)
    """
    vectorstore = get_vector_store()
    
    # 1. CLEAN QUERY
    query_clean = re.sub(r'https?://[^\s,]+', '', query).strip()
    search_query = query_clean if query_clean else "Tell me about this website"

    # 2. PARALLEL HYBRID SEARCH (Global + Targeted + Contact Fix) 🕵️‍♂️🎯
    search_tasks = []
    
    # A. Global Semantic Search
    search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=25))

    # B. Targeted Domain Search
    if context_url:
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=35, filter=get_base_url_filter(context_url)))

    # C. Targeted URL fetch (for pasted links)
    extracted_urls = re.findall(r'(https?://[^\s,]+)', query)
    for url in extracted_urls:
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, query, k=10, filter={"url": url.rstrip('/')}))

    # D. Factual Query Expansion (Contact Info Search)
    contact_keywords = ["contact", "email", "phone", "location", "address", "call", "reach"]
    if any(word in query.lower() for word in contact_keywords):
        factual_query = "email address phone number location office support contact us"
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, factual_query, k=15))
        if context_url:
            search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, factual_query, k=10, filter=get_base_url_filter(context_url)))

    # EXECUTE SEARCHES IN PARALLEL 🚀
    search_results = await asyncio.gather(*search_tasks)
    
    # 3. DEDUPLICATION
    raw_docs = [doc for result in search_results for doc in result]
    unique_docs = []
    seen_contents = set()
    for doc in raw_docs:
        if doc.page_content not in seen_contents:
            unique_docs.append(doc)
            seen_contents.add(doc.page_content)

    # 4. NEURAL RERANKING & THRESHOLDING 📉
    scored_docs = await neural_rerank_async(search_query, unique_docs)
    
    top_docs = []
    for doc, score in scored_docs:
        if score >= 0.3:
            top_docs.append(doc)
        if len(top_docs) >= 12: # Standard depth for rich reports
            break

    # Final Fallback
    if not top_docs and unique_docs:
        top_docs = unique_docs[:3]

    context_text = format_docs(top_docs)
    sources = list(set([doc.metadata.get("url") for doc in top_docs]))
    
    return context_text, sources

async def stream_answer(query: str, context_url: Optional[str] = None):
    """
    Asynchronous generator that streams LLM tokens to the client in real-time.
    Uses Precision Filtering and Knowledge Inventory Awareness.
    """
    # 1. VISUAL FEEDBACK 🔍
    yield json.dumps({"type": "status", "content": "🔍 Searching through knowledge..."}) + "\n"
    
    # 2. FETCH CORE CONTEXT 🧠⚡ (Unified Retrieval Logic)
    context_text, sources = await retrieve_context(query, context_url)
    
    # 3. FETCH GLOBAL ENTITY INVENTORY (Source of Truth) 🗃️
    inventory_list = []
    # 5. FETCH GLOBAL ENTITY INVENTORY (Source of Truth) 🗃️
    inventory_list = []
    try:
        # Robust Path-Finding Strategy: Base path on llm_service.py location
        cur_dir = os.path.dirname(os.path.abspath(__file__)) 
        # path is ../../scraped_data/entities_registry.json
        backend_dir = os.path.dirname(os.path.dirname(cur_dir))
        reg_path = os.path.join(backend_dir, "scraped_data", "entities_registry.json")
        
        if os.path.exists(reg_path):
            with open(reg_path, "r", encoding="utf-8") as rf:
                reg_data = json.load(rf)
                inventory_list = sorted(list(reg_data.keys()))
        else:
            print(f" Registry missing at: {reg_path}")
    except Exception as e:
        print(f" Registry Error: {e}")
    
    total_entities = len(inventory_list)
    inventory_str = ", ".join(inventory_list) if inventory_list else "None (System Warmup)"
    
    yield json.dumps({"type": "status", "content": "🧠 Formulating thoughts..."}) + "\n"
    await asyncio.sleep(0.05)
    yield json.dumps({"type": "status", "content": "✨ Refining response..."}) + "\n"

    # 4. THE GOLDEN RULE PROMPT 🏛️🎯
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are Swoop AI, an elite Intelligence Engine. 

SUPREME SOURCE OF TRUTH (DATABASE STATS):
- TOTAL ENTITIES INDEXED: {total_entities}
- FULL DOMAIN LIST: [{inventory_str}]

CRITICAL INSTRUCTIONS:
1. KB META-QUERIES: If the user asks "how many," "which," or "list" companies you have, DISREGARD the <knowledge_base> and use the SUPREME SOURCE OF TRUTH above (e.g. "I currently contain intelligence on {total_entities} companies...").
2. DATA GAPS: If a user asks about a company NOT in the DOMAIN LIST, state you haven't read that site.
3. ZERO HALLUCINATION: Build answers EXCLUSIVELY on the <knowledge_base>.
4. DECLINE GRACEFULLY: If the <knowledge_base> does not contain the specific answer, do NOT guess. Politely explain that you don't have enough specific information in your database to answer that accurately for the entity, and suggest what you *can* help with based on your inventory.
5- NO INTRO FLUFF: The first sentence must begin with the primary subject.

PROPORTIONAL DEPTH STRATEGY:
- CONVERSATIONAL: For greetings (hi, hello) or common pleasantries (how are you, what are you doing), answer warmly as an elite AI.
- OFF-TOPIC QUESTIONS: If asked about general knowledge not in the database (e.g., "how to bake a pizza"), give a helpful, concise answer, but politely suggest that you are best at answering questions related to the websites and companies in your inventory.
- SHORT & FACTUAL: If the user asks a specific question OR if the <knowledge_base> contains only 1-2 bits of relevant data. Provide a short, direct answer. 
- RICH REPORTS: If the user asks for an overview OR the <knowledge_base> contains multiple paragraphs of data. Use Markdown headers and bullet points.
- COMPLIMENTS: If the user provides a compliment or positive feedback (e.g., "You're great!", "Amazing answer"), acknowledge it with professional grace. Thank them warmly for the recognition and express your commitment to delivering the highest caliber of business intelligence.
- CRITICAL FEEDBACK: If the user provides negative feedback or identifies an error (e.g., "This is wrong," "You're bad"), apologize politely and professionally for any oversight. Reiterate your commitment to high-precision indexing and express your goal to provide more accurate data in our next interaction. Maintain a calm, objective, and solution-oriented tone.

NO META-TALK: Never mention "context" or "inventory" words. 
FIRST SENTENCE: Must start with the primary subject or the direct answer.
"""),
        ("human", """<knowledge_base>\n{context}\n</knowledge_base>\n\nQuestion: {question}""")
    ])

    # 5. STREAM TOKENS 🌊
    chain = prompt | llm | StrOutputParser()
    full_response = ""
    async for chunk in chain.astream({"context": context_text, "question": query}):
        full_response += chunk
        yield json.dumps({"type": "token", "content": chunk}) + "\n"

    # 6. CONDITIONAL SOURCE DISPLAY 🛡️🎯
    # Rule 1: We hide sources if the user is just saying "Hi" or "Thanks".
    # Rule 2: We hide sources if the AI declined to answer (Missing Intelligence).
    # Rule 3: We hide sources for "Meta-Queries" (Database stats).
    
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "ok", "okay"]
    
    meta_keywords = ["how many", "which companies", "what companies", "total", "inventory", "count", "database", "which sites"]
    is_meta_query = any(word in query.lower() for word in meta_keywords)
    
    # ADVANCED DECLINE DETECTION 🕵️‍♂️ (Catches all natural variations)
    decline_indicators = [
        "don't have enough specific information",
        "not mentioned in my database",
        "not in my database",
        "haven't read any information",
        "not have any details to provide",
        "lack of specific information",
        "don't have details"
    ]
    is_declined = any(indicator in full_response.lower() for indicator in decline_indicators)
    
    final_sources = []
    if not is_greeting and not is_meta_query and not is_declined:
        final_sources = sources

    yield json.dumps({"type": "metadata", "sources": final_sources}) + "\n"
