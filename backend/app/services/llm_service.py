from langchain_groq import ChatGroq
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sentence_transformers import CrossEncoder
from app.services.vector_db import get_vector_store
from app.core.config import get_settings

settings = get_settings()

# 0. Load the Neural Reranker (Extremely fast, lightweight model)
print("Loading Neural Cross-Encoder...")
reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

from typing import Optional

def format_docs(docs):
    """Utility to join document contents into a single string for the prompt."""
    return "\n\n".join(doc.page_content for doc in docs)

def neural_rerank(inputs: dict) -> dict:
    """Takes the broad Pinecone search and uses a Neural Network to strictly rank relevance."""
    query = inputs["question"]
    docs = inputs["context"]
    
    if not docs:
        return []
        
    # Score each doc against the actual user query
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker_model.predict(pairs)
    
    # Sort by score descending and take the absolute top 5
    scored_docs = list(zip(scores, docs))
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    top_docs = [doc for score, doc in scored_docs[:5]]
    return top_docs

def generate_answer(query: str, context_url: Optional[str] = None):
    """
    Modern LCEL-based RAG chain that works flawlessly with LangChain v0.3+. 
    """
    # 1. Initialize Groq LLM
    llm = ChatGroq(
        model_name=settings.LLM_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.1
    )

    # 2. Setup Vector Retrieval with Metadata Filtering
    vectorstore = get_vector_store()
    
    # Cast a wide net in Pinecone (fetch top 20), our neural reranker will prune it down to 5.
    search_kwargs = {"k": 20, "fetch_k": 40}
    # REMOVED: Domain Isolation Filter
    # if context_url:
    #     search_kwargs["filter"] = {"base_url": {"$eq": context_url}}

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs=search_kwargs
    )
    
    # Identify domain name for prompt inject
    domain_name = context_url if context_url else "this website"
    
    # 3. Create the Prompt Template
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

    # 4. Build the Chain using LCEL with Neural Reranking Step
    retrieval_chain = (
        {"context": retriever, "question": RunnablePassthrough(), "domain_name": lambda x: domain_name}
        | RunnablePassthrough.assign(context=neural_rerank)
        | RunnablePassthrough.assign(context=lambda x: format_docs(x["context"]))
    )
    
    rag_chain = (
        retrieval_chain
        | prompt
        | llm
        | StrOutputParser()
    )
    
    # 5. Run the retrieval and generation
    raw_retrieval = {"context": retriever.invoke(query), "question": query}
    top_docs = neural_rerank(raw_retrieval)
    answer = rag_chain.invoke(query)
    
    # 6. Source Formatting & Cleanup
    # Prevent displaying sources if the AI is just greeting the user or if it couldn't find info
    is_greeting = query.strip().lower() in ["hi", "hello", "hey", "how are you", "how are you?", "thanks", "thank you"]
    is_missing = "I don't have enough information" in answer or "accurate" in answer

    if is_greeting or is_missing:
        sources = []
    else:
        sources = list(set([doc.metadata.get("url") for doc in top_docs if doc.metadata.get("url")]))

    return {
        "answer": answer,
        "sources": sources
    }
