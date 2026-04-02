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
    temperature=0.0,
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
            top_n=5, 
            model='rerank-v3.5'
        )
        
        # Return document objects paired with their neural relevancy scores
        return [(docs[res.index], res.relevance_score) for res in rerank_results.results]
        
    except Exception as e:
        print(f"⚠️ Cohere Rerank Timeout/Error: {e}. Falling back to standard retrieval.")
        # Fallback: Just return the first 5 docs with a dummy high-relevance score (1.0)
        return [(doc, 1.0) for doc in docs[:5]]

def get_base_url_filter(url):
    """Utility: Robust URL filter logic (Catches URL with AND without trailing slashes!)"""
    if not url: return None
    clean = url.rstrip('/')
    return {"base_url": {"$in": [clean, clean + '/']}}

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
    # 1. HYBRID RETRIEVAL STRATEGY (Global + Targeted) 🕵️‍♂️
    # Create a "Clean" query for semantic matching (remove noisy URLs)
    query_clean = re.sub(r'https?://[^\s,]+', '', query).strip()
    search_query = query_clean if query_clean else "Tell me about this website"

    # Search Tasks Pool (We execute these in parallel for speed)
    search_tasks = []

    # A. GLOBAL SEMANTIC SEARCH (Finding answers anywhere in the DB) 🌎
    # This ensures we can answer about "Falconxoft" even while looking at "ezitech"
    search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, search_query, k=25))

    # B. TARGETED DOMAIN SEARCH (Filtering to the current site) 🎯
    if context_url:
        search_tasks.append(
            asyncio.to_thread(
                vectorstore.similarity_search, 
                search_query, 
                k=35, 
                filter=get_base_url_filter(context_url)
            )
        )

    # C. Targeted URL fetch (if a specific link was pasted in query)
    extracted_urls = re.findall(r'(https?://[^\s,]+)', query)
    if extracted_urls:
        for url in extracted_urls:
            search_tasks.append(
                asyncio.to_thread(
                    vectorstore.similarity_search, 
                    query, 
                    k=10, 
                    filter={"url": url.rstrip('/')}
                )
            )

    # D. FACTUAL QUERY EXPANSION (The "Contact Info" fix) 📞📍
    contact_keywords = ["contact", "email", "phone", "location", "address", "call", "reach"]
    if any(word in query.lower() for word in contact_keywords):
        factual_query = "email address phone number location office support contact us"
        # Search globally for contact info too
        search_tasks.append(asyncio.to_thread(vectorstore.similarity_search, factual_query, k=15))
        if context_url:
             search_tasks.append(
                asyncio.to_thread(
                    vectorstore.similarity_search, 
                    factual_query, 
                    k=10, 
                    filter=get_base_url_filter(context_url)
                )
            )

    # EXECUTE ALL SIMULTANEOUSLY 🚀
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

    # 2. NEURAL RERANKING & THRESHOLDING (THE GOLDEN STANDARD) 📈🎯
    # We ask Cohere to score the relevance of every chunk.
    scored_docs = neural_rerank({"question": search_query, "context": unique_docs})
    
    # 3. SEMANTIC FILTERING (Only keep high-relevance chunks)
    # Threshold 0.3 = Keep anything relevant.
    # We take up to 9 chunks to stay safe with the TPM limit.
    top_docs = []
    for doc, score in scored_docs:
        if score >= 0.3:
            top_docs.append(doc)
        if len(top_docs) >= 9:
            break

    # FALLBACK: If no high scores (e.g. Greetings like "Hi"), provide 2 raw chunks so the AI has entity context
    if not top_docs and unique_docs:
        top_docs = unique_docs[:2]

    context_text = format_docs(top_docs)

    # 4. SOURCE PRECISION FILTERING
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "thanks", "nice", "wow", "ok", "okay"]
    sources = list(set([doc.metadata.get("url") for doc in top_docs])) if not is_greeting else []
    
    # 5. Yield metadata first
    yield json.dumps({"type": "metadata", "sources": sources}) + "\n"

    # 6. THE GOLDEN RULE PROMPT (Role-Based for Llama 3 Architecture) 🏛️🎯
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are Swoop AI, an elite Intelligence Engine. Deliver the "Perfect Response" by adhering exclusively to the provided <knowledge_base>.

PROPORTIONAL DEPTH STRATEGY:
- CONVERSATIONAL: ONLY if the user says hello, hi, or thanks. Reply warmly. Do NOT ask how their day is.
- SHORT & FACTUAL: If the user asks a specific question OR if the <knowledge_base> contains only 1-2 sentences of relevant data. Provide a short, direct answer. 
- RICH REPORTS: ONLY if the user asks for an overview AND the <knowledge_base> contains multiple paragraphs of rich data. Use Markdown headers and bullet points.

CRITICAL RULES:
- ZERO HALLUCINATION: You are strictly forbidden from padding your answer. DO NOT invent case studies, statistics, or examples (like algorithmic trading) if they are not explicitly written in the <knowledge_base>.
- DECLINE GRACEFULLY: If the <knowledge_base> only has a vague title or lacks specific details to answer the prompt, you MUST decline. Say exactly: "My current intelligence does not contain specific details on [topic] for this entity."
- NO META-TALK: NEVER mention the "context" or your internal rules to the user.
- NO INTRO FLUFF: The first sentence must begin with the primary subject. 
"""),
        ("human", """<knowledge_base>\n{context}\n</knowledge_base>\n\nQuestion: {question}""")
    ])

    # 7. Stream tokens from the preloaded Groq LLM
    chain = prompt | llm | StrOutputParser()
    
    async for chunk in chain.astream({"context": context_text, "question": query}):
        yield json.dumps({"type": "token", "content": chunk}) + "\n"

async def generate_answer(query: str, context_url: Optional[str] = None):
    """
    Normal synchronous version for internal API calls.
    Allows for global knowledge base search while prioritizing the current context.
    """
    # 1. CLEAN QUERY
    query_clean = re.sub(r'https?://[^\s,]+', '', query).strip()
    search_query = query_clean if query_clean else "Tell me about this website"
    
    # 1. INITIALIZE VECTOR STORE
    vectorstore = get_vector_store()
    raw_docs = []

    # A. Global Semantic search (🌎 Finding patterns anywhere)
    global_docs = vectorstore.similarity_search(search_query, k=20)
    raw_docs.extend(global_docs)

    # B. Targeted Domain search (🎯 Only the current site)
    if context_url:
        targeted_docs = vectorstore.similarity_search(
            search_query, 
            k=25, 
            filter=get_base_url_filter(context_url)
        )
        raw_docs.extend(targeted_docs)
    
    # C. Targeted URL fetch
    extracted_urls = re.findall(r'(https?://[^\s,]+)', query)
    if extracted_urls:
        for url in extracted_urls:
            clean_url = url.rstrip('/')
            url_docs = vectorstore.similarity_search(query, k=10, filter={"url": clean_url})
            raw_docs.extend(url_docs)

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




