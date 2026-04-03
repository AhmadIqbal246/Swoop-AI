from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AI Website Chatbot"
    DEBUG: bool = True
    
    # AI Models
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    
    # API Keys
    GROQ_API_KEY: str
    HUGGINGFACEHUB_API_TOKEN: str
    COHERE_API_KEY: str
    PINECONE_API_KEY: str
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "chatbot-index"
    
    # Celery & Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SOCKET_TIMEOUT_SEC: int = 5
    
    # Timeouts
    LLM_TIMEOUT_SEC: int = 45
    VECTOR_SEARCH_TIMEOUT_SEC: int = 10
    SCRAPER_PAGE_TIMEOUT_SEC: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/chatbot.log"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
