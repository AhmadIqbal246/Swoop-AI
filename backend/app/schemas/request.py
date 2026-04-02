from pydantic import BaseModel, HttpUrl

class ProcessURLRequest(BaseModel):
    url: HttpUrl

from typing import Optional

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default"
    context_url: Optional[str] = None
