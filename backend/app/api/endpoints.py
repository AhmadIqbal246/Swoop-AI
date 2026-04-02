from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.core.celery_app import celery_app
from celery.result import AsyncResult
from app.services.llm_service import generate_answer, stream_answer
from app.schemas.request import ProcessURLRequest, ChatRequest
from app.schemas.response import TaskResponse, ChatResponse
from app.tasks.worker import process_url_task

router = APIRouter()

@router.post("/process-url", response_model=TaskResponse)
async def process_url(data: ProcessURLRequest):
    """
    Submits a URL to be processed in the background.
    """
    task = process_url_task.delay(str(data.url))
    return TaskResponse(
        task_id=task.id,
        status="PENDING",
        message="Website processing has started in the background."
    )

@router.get("/task-status/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    Checks the status of a background task.
    """
    result = AsyncResult(task_id, app=celery_app)
    
    response = TaskResponse(
        task_id=task_id,
        status=result.status,
    )
    
    if result.status == "SUCCESS":
        task_result = result.result or {}
        response.status = "COMPLETED" # Normalize for high-end UI detection
        response.message = task_result.get('message', 'Indexing completed!')
        response.processed_pages = task_result.get('processed_pages', [])
    elif result.status == "PENDING":
        response.status = "PENDING"
        response.message = "Initializing the Parallel Engine..."
    elif result.status == "FAILURE":
        response.status = "FAILURE"
        response.message = f"Process failed: {str(result.result)}"
    elif result.status == "PROGRESS":
        # Supports Celery custom progress if you use self.update_state in task
        task_result = result.result or {}
        response.status = "PROGRESS"
        response.message = task_result.get('message', 'Mapping content...')
        response.processed_pages = task_result.get('processed_pages', [])
    
    return response

@router.post("/chat")
async def chat(data: ChatRequest):
    """
    Answers a question by streaming tokens from the LLM in real-time.
    """
    return StreamingResponse(
        stream_answer(data.query, data.context_url),
        media_type="text/event-stream"
    )
