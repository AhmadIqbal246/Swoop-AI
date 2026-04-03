from pydantic import BaseModel, HttpUrl, Field, validator
from typing import Optional
from app.core.config import get_settings

settings = get_settings()

class ProcessURLRequest(BaseModel):
    # Fix 2.1: Robust URL constraints
    url: str = Field(..., max_length=settings.MAX_URL_LENGTH)

    @validator("url")
    def validate_url_security(cls, v):
        # 1. Basic URL pattern check
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        
        # 2. SSRF Protection: Forbidden internal domains
        v_low = v.lower()
        if any(d in v_low for d in settings.FORBIDDEN_DOMAINS):
            raise ValueError("Access to internal/restricted network addresses is forbidden.")
        
        # 3. Path protection (Admin/Internal)
        forbidden_paths = ["/admin", "/api", "/internal", "/server-status"]
        if any(p in v_low for p in forbidden_paths):
            raise ValueError("Scraping internal administrative paths is forbidden.")
            
        return v

class ChatRequest(BaseModel):
    # Fix 2.2: Query length validation
    query: str = Field(..., min_length=1, max_length=settings.MAX_QUERY_LENGTH)
    
    # Fix 2.3: Session ID validation (Security/Pathing)
    session_id: str = Field(..., min_length=1, max_length=settings.MAX_SESSION_ID_LENGTH)
    
    context_url: Optional[str] = None
    clear_history: Optional[bool] = False

    @validator("session_id")
    def validate_session_format(cls, v):
        # Prevent path traversal: Alpha-numeric, hyphens, and underscores only.
        import re
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("Session ID must contain only alphanumeric characters, hyphens, or underscores.")
        return v
