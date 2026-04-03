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
print("Engine Warming Up: Preloading LLM & Embeddings...")
llm = ChatGroq(
    model_name=settings.LLM_MODEL,
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.1, # Increased slightly for more natural variation
    streaming=True
)

def format_docs(docs: List[Any]) -> str:
    """Enhanced Formatter: Injects source context into each chunk to prevent cross-site hallucination."""
    formatted = []
    for doc in docs:
        url = doc.metadata.get("url", "Unknown Source")
        formatted.append(f"### [DOCUMENT SOURCE: {url}]\n{doc.page_content}")
    return "\n\n---\n\n".join(formatted)

async def neural_rerank_async(query: str, docs: List[Any]) -> List[Tuple[Any, float]]:
    """
    Asynchronous wrapper for Cohere's Rerank API.
    Returns a list of (document_object, relevance_score) tuples.
    """
    if not docs:
        return []

    texts = [doc.page_content for doc in docs]
    
    try:
        rerank_results = await asyncio.to_thread(
            co.rerank,
            query=query, 
            documents=texts, 
            top_n=15, # Increased the top_n for richer context
            model='rerank-v3.5'
        )
        return [(docs[res.index], res.relevance_score) for res in rerank_results.results]
    except Exception as e:
        print(f"⚠️ Cohere Rerank Timeout/Error: {e}. Falling back.")
        return [(doc, 1.0) for doc in docs[:10]]

def get_base_url_filter(url: str) -> Optional[Dict[str, Any]]:
    """Utility: Robust URL filter logic (Catches URL with AND without trailing slashes!)"""
    if not url: return None
    clean = url.rstrip('/')
    return {"base_url": {"$in": [clean, clean + '/']}}

async def condense_query(query: str, history_str: str) -> str:
    """
    ELITE CONDENSER:
    Outputs a standalone search query. We also add an INTENT tag for short-circuiting.
    """
    if not history_str:
        return re.sub(r'https?://[^\s,]+', '', query).strip() or "General inquiry"

    condense_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a Query Architect. Re-write the user's question into a standalone, detailed search query. 
         If the question is just a greeting, a compliment, or a name-telling statement, prefix your output with [GREETING]."""),
        ("human", f"Chat History:\n{history_str}\n\nNew Question: {query}")
    ])
    
    chain = condense_prompt | llm | StrOutputParser()
    standalone = await chain.ainvoke({})
    return standalone.strip()

async def retrieve_context(query_str: str, context_url: Optional[str] = None) -> Tuple[str, List[str], float]:
    """
    CORE RETRIEVAL ENGINE 🧠⚡
    Now returns (context_text, sources, max_score) for Source Visibility control.
    """
    # SHORT-CIRCUIT: Skip vector search for greetings (Speed Boost 🚀)
    if "[GREETING]" in query_str:
        return "", [], 0.0

    vectorstore = get_vector_store()
    search_query = query_str.replace("[GREETING]", "").strip()

    # 1. PARALLEL TRIPLE-THREAT SEARCH 🕵️‍♂️🎯
    search_tasks = []
    search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=50)) # Increased k for wider search
    if context_url:
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=50, filter=get_base_url_filter(context_url)))
    
    contact_keywords = ["contact", "email", "phone", "location", "address", "pricing", "cost"]
    if any(word in search_query.lower() for word in contact_keywords):
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, "contact details email phone pricing plans cost", k=30))

    search_results = await asyncio.gather(*search_tasks)
    
    # 2. DEDUPLICATION
    raw_docs = [doc for result in search_results for doc in result]
    unique_docs = []
    seen_contents = set()
    for doc in raw_docs:
        if doc.page_content not in seen_contents:
            unique_docs.append(doc)
            seen_contents.add(doc.page_content)

    # 3. NEURAL RERANKING & THRESHOLDING 📉
    scored_docs = await neural_rerank_async(search_query, unique_docs)
    
    top_docs = []
    max_score = 0.0
    if scored_docs:
        max_score = scored_docs[0][1]

    # COMPROMISE: We need to stay under Groq 6,000 TPM limit.
    # We will take Top 8 high-quality docs instead of 15.
    current_tokens = 0
    for doc, score in scored_docs:
        if score >= 0.15: 
            # Simple heuristic: 1 char ~= 0.25 tokens. 
            # We want to keep context under ~3500 tokens (14,000 chars)
            char_len = len(doc.page_content)
            if current_tokens + (char_len // 4) < 3500:
                top_docs.append(doc)
                current_tokens += (char_len // 4)
        if len(top_docs) >= 8: break

    context_text = format_docs(top_docs)
    sources = list(set([doc.metadata.get("url") for doc in top_docs]))
    
    return context_text, sources, max_score

async def stream_answer(query: str, session_id: str, context_url: Optional[str] = None):
    """
    Asynchronous generator that streams LLM tokens with Hyper-Intelligent Source Display.
    """
    # 1. LOAD MEMORY & CHECK HARDCODE SKIP 🏎️
    history_str = HistoryManager.get_history_as_string(session_id)
    profile = HistoryManager.get_profile(session_id)
    user_name = profile.get("name", "User")
    
    # Simple hardcoded check for instant responses
    normalized = query.strip().lower()
    if normalized in ["hi", "hello", "hey", "how are you", "thanks", "ok", "okay", "thanks!"]:
        context_text, sources, max_score = "", [], 0.0
    else:
        yield json.dumps({"type": "status", "content": "🔍 Analyzing conversation..."}) + "\n"
        # 2. FETCH CORE CONTEXT 🧠⚡ (Includes AI-Condensing step)
        search_query = await condense_query(query, history_str)
        context_text, sources, max_score = await retrieve_context(search_query, context_url)
    
    # 3. GLOBAL ENTITY INVENTORY (Source of Truth)
    inventory_list = []
    try:
        cur_dir = os.path.dirname(os.path.abspath(__file__)) 
        backend_dir = os.path.dirname(os.path.dirname(cur_dir))
        reg_path = os.path.join(backend_dir, "scraped_data", "entities_registry.json")
        if os.path.exists(reg_path):
            with open(reg_path, "r", encoding="utf-8") as rf:
                reg_data = json.load(rf)
                inventory_list = sorted(list(reg_data.keys()))
    except Exception: pass
    
    total_entities = len(inventory_list)
    inventory_str = ", ".join(inventory_list) if inventory_list else "None (System Warmup)"
    
    yield json.dumps({"type": "status", "content": "🧠 Synthesizing response..."}) + "\n"

    # DEBUG: See what is actually being sent to the AI 🕵️‍♂️
    print(f"--- DEBUG: CONTEXT LOADED ({len(context_text)} chars) for user query '{query}' ---")

    # 4. THE PROMPT 🏛️🎯
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are Swoop AI, an elite Intelligence Engine. 

CURRENT SESSION PROFILE:
- USER NAME: {user_name}
- TOTAL ENTITIES INDEXED: {total_entities}
- FULL DOMAIN LIST: [{inventory_str}]

STRICT RULES (FAILURE IS UNACCEPTABLE):
1. ZERO META-TALK: Never mention "provided info," "knowledge base," "context," or "records." Do NOT say "according to the doc" or "I couldn't find."
2. PROPORTIONAL DEPTH: For Overviews or Detailed questions, provide structured paragraphs with Markdown formatting (bullet points, headers). 
3. MISSING INFO STRATEGY: If a fact (like a phone number or CEO) is missing, say "The CEO is not listed for FalconXoft" instead of "I don't have that info." Always try to "bridge" to a related fact (e.g., "The CEO is not listed, but the Founder is Dawar").
4. HISTORY OVERRIDE: The <knowledge_base> is the ONLY source of truth. If history is wrong, correct it based on current context.
5. IDENTITY AWARENESS: Distinguish between "Your Company" (FalconXoft) and other companies using the ### [DOCUMENT SOURCE] tag.
6. CONCISE ACKNOWLEDGEMENTS: Respond with a short, 1-sentence reply for simple acknowledgements.
7. NO INTRO FLUFF: Do NOT start with "Here is..." or "Based on...". Start with the direct answer.
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
    
    if "my name is " in query.lower():
        extracted_name = query.lower().split("my name is ")[1].title().split()[0].replace(".", "").replace("!", "")
        HistoryManager.store_fact(session_id, "name", extracted_name)

    # 7. NEURAL SOURCE DISPLAY 🛡️🎯
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "ok", "okay", "nice to meet you"]
    is_identity = "my name is" in query.lower() or "remember my name" in query.lower()
    
    final_sources = []
    # LOWERED DISPLAY THRESHOLD TO 0.25: Shows sources more often but keeps greetings clean.
    if max_score > 0.25 and not is_greeting and not is_identity:
        if "don't have enough specific information" not in full_response.lower():
            final_sources = sources

    yield json.dumps({"type": "metadata", "sources": final_sources}) + "\n"
