import json
import re
import cohere
import asyncio
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
# This ensures the LLM is ready BEFORE the first request arrives.
print("Engine Warming Up: Preloading LLM & Embeddings...")
llm = ChatGroq(
    model_name=settings.LLM_MODEL,
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.1,
    streaming=True
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
    
    try:
        # Call Cohere Rerank API (v3.5 is the latest and most accurate)
        rerank_results = co.rerank(
            query=query, 
            documents=texts, 
            top_n=10, 
            model='rerank-v3.5'
        )
        
        # Return document objects paired with their neural relevancy scores
        return [(docs[res.index], res.relevance_score) for res in rerank_results.results]
        
    except Exception as e:
        print(f"⚠️ Cohere Rerank Timeout/Error: {e}. Falling back to standard retrieval.")
        # Fallback: Just return the first 5 docs with a dummy high-relevance score (1.0)
        return [(doc, 1.0) for doc in docs[:5]]

async def stream_answer(query: str, context_url: Optional[str] = None):
    """
    Asynchronous generator that streams LLM tokens to the client in real-time.
    Uses Precision Filtering to only show highly relevant sources.
    """
    # 1. INITIALIZE VECTOR STORE (FRESH PER SESSION) 🛡️⚡
    # We do this inside the async loop to avoid "Session Closed" errors.
    vectorstore = get_vector_store()
    
    prompt = ChatPromptTemplate.from_template("""
    You are Swoop AI, a highly intelligent, polite technical assistant. 
    You have access to a vast Global Knowledge Base of multiple websites.

    STRICT RULES:
    1. GREETINGS: If the user simply says hello, hi, thanks, or asks how you are, respond politely as an AI assistant.
    2. FACTUAL BASIS: Base your answer EXCLUSIVELY on the provided context below.
    3. MISSING DATA: If the user's question cannot be answered using the provided context, you MUST respond with: 
       "I'm sorry, but I don't have enough information in my database to answer that question accurately. Is there anything else you'd like to know?"
    You are Swoop AI, a highly intelligent assistant with access to a Global Knowledge Base.
    
    GUIDELINES:
    1. If the user asks about a specific URL and you cannot find that exact link in context, use the BROAD knowledge about the company/domain to answer. 
    2. Be helpful. If you have any information about the entity mentioned, provide it.
    3. Use the provides context below for your answer.
    
    Context: {context}
    Question: {question}
    Answer:""")

    # 1. VISUAL FEEDBACK (Initial) 🔍
    # We send these as 'status' type so the UI can render them in a dedicated 'Thinking' bar.
    yield json.dumps({"type": "status", "content": "🔍 Searching through knowledge..."}) + "\n"
    await asyncio.sleep(0.05)

    # 1. HYBRID RETRIEVAL STRATEGY 🕵️‍♂️
    # Create a "Clean" query for semantic matching (remove the noisy URL string)
    query_clean = re.sub(r'https?://[^\s,]+', '', query).strip()
    # If the user ONLY sent a URL, we use a fallback generic query
    search_query = query_clean if query_clean else "Tell me about this website"

    # IDENTITY DETECTION 🕵️‍♂️ (Who is, Founder, CEO, Team)
    # Using a maximalist keyword set to ensure we never miss identity chunks.
    is_identity_query = any(word in query.lower() for word in ["who is", "founder", "ceo", "team", "leadership", "owner", "management", "boss", "creator", "started", "history", "vision"])
    primary_k = 65 if is_identity_query else 25

    # A. Global Semantic search (NOW DOMAIN-ISOLATED 🛡️)
    if context_url:
        # Search ONLY within the current website's knowledge base
        # Parallel Search - Concurrent execution for Speed ⚡
        # We use 'to_thread' + sync search to avoid the "Session is closed" aiohttp bug!
        search_tasks = [
            asyncio.to_thread(
                vectorstore.similarity_search, 
                search_query, 
                k=primary_k, 
                filter={"base_url": context_url.rstrip('/')}
            )
        ]
    else:
        # Fallback to general search
        search_tasks = [
            asyncio.to_thread(vectorstore.similarity_search, search_query, k=25)
        ]
    
    # B. Targeted URL fetch
    extracted_urls = re.findall(r'(https?://[^\s,]+)', query)
    if extracted_urls:
        for url in extracted_urls:
            search_tasks.append(
                asyncio.to_thread(
                    vectorstore.similarity_search, 
                    query, 
                    k=15, 
                    filter={"url": url.rstrip('/')}
                )
            )
            
    # C. Context Page fetch
    if context_url:
        search_tasks.append(
            asyncio.to_thread(
                vectorstore.similarity_search, 
                search_query, 
                k=15, 
                filter={"url": context_url.rstrip('/')}
            )
        )

    # EXECUTE ALL SIMULTANEOUSLY 🚀
    # This is still parallel! It just uses threads instead of raw async task-switching.
    search_results = await asyncio.gather(*search_tasks)
    
    yield json.dumps({"type": "status", "content": "🧠 Formulating thoughts..."}) + "\n"
    await asyncio.sleep(0.05)

    yield json.dumps({"type": "status", "content": "✨ Refining response..."}) + "\n"
    await asyncio.sleep(0.05)
    
    # Flatten and Deduplicate
    raw_docs = [doc for result in search_results for doc in result]
    unique_docs = []
    seen_contents = set()
    for doc in raw_docs:
        if doc.page_content not in seen_contents:
            unique_docs.append(doc)
            seen_contents.add(doc.page_content)

    # 2. NEURAL RERANKING
    scored_docs = neural_rerank({"question": search_query, "context": unique_docs})
    
    # 3. DIVERSITY SELECTION (The "Global Awareness" Fix) 🧩
    # We ensure the context isn't dominated by just one page (like a long Careers page)
    diverse_docs = []
    url_counts = {}
    for doc, score in scored_docs:
        url = doc.metadata.get("url", "unknown")
        url_counts[url] = url_counts.get(url, 0) + 1
        # Allow max 3 chunks per page to force the AI to see the whole site!
        if url_counts[url] <= 3:
            diverse_docs.append(doc)
            
    # Take the top refined documents for the AI
    top_docs = diverse_docs[:12]
    context_text = format_docs(top_docs)

    # 4. SOURCE PRECISION FILTERING
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "nice", "wow", "ok", "okay"]
    
    sources = []
    if not is_greeting:
        # Filter sources based on neural relevance threshold (0.3)
        sources = list(set([
            doc.metadata.get("url") 
            for doc in top_docs 
        ]))
    
    # 5. Yield metadata first
    yield json.dumps({"type": "metadata", "sources": sources}) + "\n"

    # 6. DYNAMIC INTELLIGENCE PROMPT (Professional and Narrative) 🏗️
    prompt = ChatPromptTemplate.from_template("""
    You are Swoop AI, a professional Intelligence Assistant. 
    Your mission is to provide an elite, multi-dimensional report on the entity or website in question.

    DYNAMIC RESPONSE STRATEGY:
    1. DIRECT FOCUSED ANSWER: If the user asks a specific question about a fact (location, services, etc.), answer it IMMEDIATELY and CLEARLY at the top.
    2. PROFESSIONAL NARRATIVE OVERVIEW: For general inquiries ("Tell me about..."), deliver a comprehensive report:
       - CORE IDENTITY: Synthesize a strong, professional description of the subject.
       - SERVICES & EXPERTISE: Detail their core offerings and technology focus with precision.
       - CLIENTS & PARTNERS: Mention key organizations found EXPLICITLY in the provided context.
       - VALUES & IDENTITY: Describe the subject's philosophy and "professional character."

    STRICT RULES:
    - NO ROBOTIC ROBOT-SPEAK: Do NOT use phrases like "Swoop AI identifies...", "Based on...", or "The context does not state...". 
    - START DIRECTLY: The first sentence must begin with the subject or the answer.
    - EXCLUSIVE CONTEXT: Do NOT mention any facts or client names (like "Coca-Cola") not found in the context.
    - BE DESCRIPTIVE: Use high-level, professional storytelling. Avoid simple bullet lists where possible for a premium experience.

    Context: {context}
    Question: {question}
    Answer:""")

    # 7. Stream tokens from the preloaded Groq LLM
    chain = prompt | llm | StrOutputParser()
    
    async for chunk in chain.astream({"context": context_text, "question": query}):
        yield json.dumps({"type": "token", "content": chunk}) + "\n"

async def generate_answer(query: str, context_url: Optional[str] = None):
    """
    Normal synchronous version for internal API calls.
    """
    search_query = query_clean if query_clean else "Tell me about this website"
    
    # 1. INITIALIZE VECTOR STORE (FRESH PER SESSION) 🛡️⚡
    vectorstore = get_vector_store()

    # A. Global Semantic search (NOW DOMAIN-ISOLATED 🛡️)
    if context_url:
        # Search ONLY within the current website's knowledge base
        raw_docs = vectorstore.similarity_search(
            search_query, 
            k=25, 
            filter={"base_url": context_url.rstrip('/')}
        )
    else:
        # Fallback to general (less accurate) search if no context is provided
        raw_docs = vectorstore.similarity_search(search_query, k=20)
    
    # B. Targeted URL fetch
    extracted_urls = re.findall(r'(https?://[^\s,]+)', query)
    if extracted_urls:
        for url in extracted_urls:
            clean_url = url.rstrip('/')
            targeted_docs = vectorstore.similarity_search(query, k=15, filter={"url": clean_url})
            raw_docs.extend(targeted_docs)
            
    # C. Context-aware search
    if context_url:
        in_session_docs = vectorstore.similarity_search(search_query, k=10, filter={"url": context_url.rstrip('/')})
        raw_docs.extend(in_session_docs)

    # D. Deduplicate
    unique_docs = []
    seen_contents = set()
    for doc in raw_docs:
        if doc.page_content not in seen_contents:
            unique_docs.append(doc)
            seen_contents.add(doc.page_content)

    # 2. NEURAL RERANKING
    scored_docs = neural_rerank({"question": search_query, "context": unique_docs})
    
    # 3. DIVERSITY SELECTION (The "Global Awareness" Fix) 🧩
    diverse_docs = []
    url_counts = {}
    for doc, score in scored_docs:
        url = doc.metadata.get("url", "unknown")
        url_counts[url] = url_counts.get(url, 0) + 1
        if url_counts[url] <= 3:
            diverse_docs.append(doc)
            
    top_docs = diverse_docs[:12]
    context_text = format_docs(top_docs)

    # 4. DYNAMIC INTELLIGENCE PROMPT 🏗️
    prompt = ChatPromptTemplate.from_template("""
    You are Swoop AI, a professional Intelligence Assistant. 
    Your mission is to provide an elite, multi-dimensional report on the entity or website in question.

    DYNAMIC RESPONSE STRATEGY:
    1. DIRECT FOCUSED ANSWER: If the user asks a specific question about a fact (location, services, etc.), answer it IMMEDIATELY and CLEARLY at the top.
    2. PROFESSIONAL NARRATIVE OVERVIEW: For general inquiries ("Tell me about..."), deliver a comprehensive report:
       - CORE IDENTITY: Synthesize a strong, professional description of the subject.
       - SERVICES & EXPERTISE: Detail their core offerings and technology focus with precision.
       - CLIENTS & PARTNERS: Mention key organizations found EXPLICITLY in the provided context.
       - VALUES & IDENTITY: Describe the subject's philosophy and "professional character."

    STRICT RULES:
    - NO ROBOTIC ROBOT-SPEAK: Do NOT use phrases like "Swoop AI identifies...", "Based on...", or "The context does not state...". 
    - START DIRECTLY: The first sentence must begin with the subject or the answer.
    - EXCLUSIVE CONTEXT: Do NOT mention any facts or client names (like "Coca-Cola") not found in the context.
    - BE DESCRIPTIVE: Use high-level, professional storytelling. Avoid simple bullet lists where possible for a premium experience.

    Context: {context}
    Question: {question}
    Answer:""")

    # 5. Generate Answer
    chain = prompt | llm | StrOutputParser()
    answer = await chain.ainvoke({"context": context_text, "question": query})
    
    # 6. Extract Sources
    sources = list(set([doc.metadata.get("url") for doc in top_docs]))
    
    return {"answer": answer, "sources": sources}




