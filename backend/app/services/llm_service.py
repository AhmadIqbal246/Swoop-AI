import json
import os
import re
import cohere
import asyncio
import time
from typing import Optional, List, Dict, Any, Tuple
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from app.services.vector_db import get_vector_store
from app.core.config import get_settings
from app.services.history_service import HistoryManager
from app.core.logging import app_logger as logger 
from app.utils.domain_tools import extract_urls_from_query, normalize_to_domain

settings = get_settings()

# Initialize Cohere Client
co = cohere.Client(api_key=settings.COHERE_API_KEY)

# GLOBAL INITIALIZATION 🚀
llm = ChatGroq(
    model_name=settings.LLM_MODEL,
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.1,
    streaming=True
)

def format_docs(docs: List[Any]) -> str:
    formatted = []
    for doc in docs:
        url = doc.metadata.get("url", "Unknown Source")
        formatted.append(f"### [DOCUMENT SOURCE: {url}]\n{doc.page_content}")
    return "\n\n---\n\n".join(formatted)

async def neural_rerank_async(query: str, docs: List[Any]) -> List[Tuple[Any, float]]:
    if not docs:
        return []
    texts = [doc.page_content for doc in docs]
    try:
        rerank_results = await asyncio.to_thread(
            co.rerank,
            query=query, 
            documents=texts, 
            top_n=10,
            model='rerank-v3.5'
        )
        return [(docs[res.index], res.relevance_score) for res in rerank_results.results]
    except Exception:
        logger.error("Cohere Rerank error or timeout", exc_info=True)
        return [(doc, 1.0) for doc in docs[:8]]

def get_base_url_filter(url: str) -> Optional[Dict[str, Any]]:
    if not url: return None
    clean = url.rstrip('/')
    return {"base_url": {"$in": [clean, clean + '/']}}

async def condense_query(query: str, history_str: str) -> str:
    if not history_str:
        return re.sub(r'https?://[^\s,]+', '', query).strip() or "General inquiry"
    condense_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Query Architect. Re-write the user's question into a standalone, detailed search query."),
        ("human", f"Chat History:\n{history_str}\n\nNew Question: {query}")
    ])
    chain = condense_prompt | llm | StrOutputParser()
    standalone = await chain.ainvoke({})
    return standalone.strip()

async def retrieve_context(query_str: str, context_url: Optional[str] = None) -> Tuple[str, List[str], float]:
    if "[GREETING]" in query_str:
        return "", [], 0.0
    vectorstore = get_vector_store()
    search_query = query_str.replace("[GREETING]", "").strip()
    search_tasks = [asyncio.to_thread(vectorstore.similarity_search, search_query, k=30)]
    if context_url:
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=30, filter=get_base_url_filter(context_url)))
    
    try:
        search_results = await asyncio.wait_for(asyncio.gather(*search_tasks), timeout=settings.VECTOR_SEARCH_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        logger.error("Vector search timeout occurred")
        return "", [], 0.0
    
    raw_docs = [doc for result in search_results for doc in result]
    unique_docs = []
    seen = set()
    for d in raw_docs:
        if d.page_content not in seen:
            unique_docs.append(d)
            seen.add(d.page_content)

    scored_docs = await neural_rerank_async(search_query, unique_docs)
    top_docs = []
    max_score = scored_docs[0][1] if scored_docs else 0.0
    curr_tokens = 0
    for doc, score in scored_docs:
        if score >= 0.15:
            if curr_tokens + (len(doc.page_content)//4) < 3500:
                top_docs.append(doc)
                curr_tokens += (len(doc.page_content)//4)
        if len(top_docs) >= 8: break

    return format_docs(top_docs), list(set([doc.metadata.get("url") for doc in top_docs])), max_score

async def stream_answer(query: str, session_id: str, context_url: Optional[str] = None):
    # 1. AUTO-DISCOVERY INTERCEPTOR 🕵️‍♂️🎯
    detected_domains = extract_urls_from_query(query)
    auto_context_url = context_url

    if detected_domains:
        target_domain = detected_domains[0]
        reg_path = "scraped_data/entities_registry.json"
        is_known = False
        if os.path.exists(reg_path):
            with open(reg_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                if target_domain in registry:
                    is_known = True
                    auto_context_url = registry[target_domain]["url"]
        
        if not is_known:
            yield json.dumps({"type": "status", "content": f"📡 New domain detected: {target_domain}. Initializing research sweep..."}) + "\n"
            from app.tasks.worker import process_url_task
            from celery.result import AsyncResult
            from app.core.celery_app import celery_app
            discovery_url = f"https://{target_domain}"
            task = process_url_task.delay(discovery_url)
            auto_context_url = discovery_url
            
            start_wait = time.time()
            last_msg = ""
            while True:
                res = AsyncResult(task.id, app=celery_app)
                if res.status == "SUCCESS":
                    yield json.dumps({"type": "status", "content": "✅ Research complete. Synthesizing overview..."}) + "\n"
                    break
                elif res.status == "FAILURE":
                    yield json.dumps({"type": "status", "content": "❌ Research failed. Attempting general response..."}) + "\n"
                    break
                elif res.status == "PROGRESS":
                    curr_msg = res.result.get('message', 'Analyzing...')
                    if curr_msg != last_msg:
                        yield json.dumps({"type": "status", "content": f"📡 {curr_msg}"}) + "\n"
                        last_msg = curr_msg
                if time.time() - start_wait > 90:
                    yield json.dumps({"type": "status", "content": "⏳ Research timed out. Continuing..."}) + "\n"
                    break
                await asyncio.sleep(2)

    # 2. LOAD MEMORY & CHECK SKIP
    history_str = HistoryManager.get_history_as_string(session_id)
    profile = HistoryManager.get_profile(session_id)
    user_name = profile.get("name", "User")
    
    normalized = query.strip().lower()
    if normalized in ["hi", "hello", "hey", "how are you", "thanks", "ok", "okay"]:
        context_text, sources, max_score = "", [], 0.0
    else:
        yield json.dumps({"type": "status", "content": "🔍 Analyzing conversation..."}) + "\n"
        search_query = await condense_query(query, history_str)
        context_text, sources, max_score = await retrieve_context(search_query, auto_context_url)
    
    # 3. ENTITY INVENTORY
    inventory_list = []
    try:
        reg_path = "scraped_data/entities_registry.json"
        if os.path.exists(reg_path):
            with open(reg_path, "r", encoding="utf-8") as rf:
                inventory_list = sorted(list(json.load(rf).keys()))
    except Exception: pass
    
    total_entities = len(inventory_list)
    inventory_str = ", ".join(inventory_list) if inventory_list else "None"
    
    yield json.dumps({"type": "status", "content": "🧠 Synthesizing response..."}) + "\n"
    logger.info("Starting synthesis", extra={"session_id": session_id})

    # 4. PROMPT & STREAM
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"You are Swoop AI. Name: {user_name}. Indexed: {inventory_str}. Total: {total_entities}. Never mention provided info. Be direct."),
        ("human", f"<history>\n{history_str}\n</history>\n\n<context>\n{{context}}\n</context>\n\nQuestion: {{question}}")
    ])

    chain = prompt | llm | StrOutputParser()
    full_response = ""
    astreamer = chain.astream({"context": context_text, "question": query})
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(anext(astreamer), timeout=settings.LLM_TIMEOUT_SEC)
                full_response += chunk
                yield json.dumps({"type": "token", "content": chunk}) + "\n"
            except StopAsyncIteration: break
    except asyncio.TimeoutError:
        yield json.dumps({"type": "token", "content": "\n\n⚠️ Response timeout."}) + "\n"

    # 5. STORAGE & SOURCES
    HistoryManager.add_message(session_id, "user", query)
    HistoryManager.add_message(session_id, "assistant", full_response)
    
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "thanks"]
    final_sources = sources if (max_score > 0.25 and not is_greeting) else []
    yield json.dumps({"type": "metadata", "sources": final_sources}) + "\n"
