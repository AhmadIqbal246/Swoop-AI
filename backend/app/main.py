from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG
)

# Return 429 Too Many Requests if limited
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware (RESTORED 🛡️)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    """Fix 7.1: Centralized Health Check for all core dependencies."""
    from app.services.history_service import HistoryManager
    from app.services.vector_db import get_vector_store
    
    health = {"status": "ok", "app": settings.APP_NAME, "services": {}}
    
    # Check Redis
    try:
        HistoryManager.redis_client.ping()
        health["services"]["redis"] = "connected"
    except Exception:
        health["services"]["redis"] = "disconnected"
        health["status"] = "degraded"

    # Check Pinecone (Simplified check by getting index stats)
    try:
        get_vector_store()
        health["services"]["vector_db"] = "ready"
    except Exception:
        health["services"]["vector_db"] = "error"
        health["status"] = "degraded"

    return health

# Include API Router
app.include_router(api_router, prefix="/api/v1")
