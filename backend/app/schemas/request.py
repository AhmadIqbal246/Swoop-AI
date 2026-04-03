from pydantic import BaseModel, HttpUrl

class ProcessURLRequest(BaseModel):
    url: HttpUrl

from typing import Optional

class ChatRequest(BaseModel):
    query: str
    session_id: str
    context_url: Optional[str] = None
    clear_history: Optional[bool] = False
