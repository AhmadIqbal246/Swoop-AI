# AI Website Chatbot (RAG-Powered)

.\venv\Scripts\python -m celery -A app.core.celery_app worker --pool=threads --loglevel=info 
.\venv\Scripts\python -m uvicorn app.main:app --reload


An AI Chatbot that answers questions strictly based on the content of a user-provided URL.

## 🚀 Key Features
- **URL-to-Knowledge**: Provide any URL, and the AI will scrape, index, and learn from it.
- **Strict Context Answering**: The AI is programmed to answer *only* using information from the provided website. 
- **Background Processing**: Uses Celery & Redis to handle heavy scraping and vectorizing tasks without slowing down the UI.
- **Free Vectors & Chat**: Uses HuggingFace `all-MiniLM-L6-v2` (Local) and `Mistral-7B` (Free Hub) models.

## 🛠️ Tech Stack
- **Frontend**: React 18 + Vite (Clean, minimal, high-performance UI)
- **Backend**: FastAPI (Python) (Fast, asynchronous, AI-first API)
- **Vector Database**: Pinecone (Managed vector indexes)
- **Background Tasks**: Celery + Redis (Reliable task queuing & retries)

---

## 📂 Project Structure

### Backend (`/backend`)
```text
backend/
├── app/
│   ├── api/
│   │   ├── deps.py          # Centralized client initializers (OpenAI, Pinecone)
│   │   ├── endpoints.py     # Clean route handlers (triggering background tasks)
│   │   └── router.py        # API router aggregation
│   ├── core/
│   │   ├── config.py        # Validates and loads Environment Variables
│   │   ├── celery_app.py    # Celery configuration (Broker/Backend setup)
│   │   └── logging.py       # Custom log formatters
│   ├── schemas/
│   │   ├── request.py       # Input validation: URL/Chat models
│   │   └── response.py      # Output structure: Status and AI messages
│   ├── services/
│   │   ├── scraper.py       # Playwright engine for text extraction
│   │   ├── vector_db.py     # Pinecone search and index logic
│   │   └── openai_llm.py    # OpenAI embedding and chat logic
│   ├── tasks/
│   │   └── worker.py        # Celery task definitions (The "Engine")
│   ├── utils/
│   │   ├── text_cleanup.py  # Cleans HTML/JS boilerplate
│   │   └── chunking.py      # Splits text into context-rich pieces
│   └── main.py              # Application entry point & CORS config
├── .env                     # Secrets (PINECONE_KEY, OPENAI_KEY, REDIS_URL)
└── requirements.txt         # Dependencies
```

### Frontend (`/frontend`)
```text
frontend/
├── src/
│   ├── components/         # UI blocks: ChatInput, ChatBox, Message, Navbar
│   ├── hooks/              # Custom React hooks: useChat, useCrawler
│   ├── services/           # Backend API communication (Axios)
│   ├── styles/             # Global CSS & Design Tokens (Glassmorphism)
│   ├── assets/             # Brand logos & background animations
│   ├── App.jsx             # Main layout & logic orchestration
│   └── main.jsx            # Entry point
├── index.html              # Template with font imports
├── vite.config.js          # Fast build/dev configuration
└── package.json            # Frontend dependencies
```

---

## ⚙️ Initial Setup Guide

### 1. Requirements
- Python 3.9+
- Node.js 18+
- Redis (as the message broker for Celery)
- OpenAI API Key
- Pinecone API Key

### 2. Backend Setup
1. Create a virtual environment and install requirements:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```
2. Configure `.env` with your API keys and `REDIS_URL`.
3. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Start the Celery worker:
   ```bash
   celery -A app.core.celery_app worker --loglevel=info
   ```

### 3. Frontend Setup
1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start the dev server:
   ```bash
   npm run dev
   ```

---

## 🛠️ RAG Pipeline Summary
1. **Fetch**: Extract text using `Playwright` to handle SPA/JS websites.
2. **Process**: Clean text and split it into chunks (~800 tokens with 10% overlap).
3. **Index**: Embed chunks with HuggingFace **`all-MiniLM-L6-v2`** (local, free) and store in Pinecone (**384 Dim**).
4. **Chat**: Retrieve the top 5 most relevant chunks from Pinecone.
5. **Generate**: Provide those chunks to **`Mistral-7B`** (via HuggingFace Hub) to generate a free answer.
