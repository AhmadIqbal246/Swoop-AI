from pydantic import BaseModel, HttpUrl
from typing import Optional, List

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: Optional[str] = None
    processed_pages: Optional[List[str]] = None

class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = None
    status: str = "success"
