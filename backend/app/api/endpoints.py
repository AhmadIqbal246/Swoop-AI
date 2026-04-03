from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.core.celery_app import celery_app
from celery.result import AsyncResult
from app.services.llm_service import stream_answer
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
        # 🛡️ CATCH SOFT-REVOKES (When the worker stopped itself)
        if task_result.get('status') == 'REVOKED':
            response.status = "REVOKED"
            response.message = task_result.get('message', 'Process stopped.')
            response.processed_pages = task_result.get('processed_pages', [])
        else:
            response.status = "COMPLETED" # Normalize for high-end UI detection
            response.message = task_result.get('message', 'Indexing completed!')
            response.processed_pages = task_result.get('processed_pages', [])
    elif result.status == "REVOKED":
        response.status = "REVOKED"
        response.message = "The process was revoked."
    elif result.status == "PENDING":
        response.status = "PENDING"
        response.message = "Initializing the Parallel Engine..."
    elif result.status == "FAILURE":
        response.status = "FAILURE"
        response.message = f"Process failed: {str(result.result)}"
    elif result.status == "PROGRESS":
        task_result = result.result or {}
        response.status = "PROGRESS"
        response.message = task_result.get('message', 'Mapping content...')
        response.processed_pages = task_result.get('processed_pages', [])
    
    return response

@router.post("/stop-task/{task_id}", response_model=TaskResponse)
async def stop_task(task_id: str):
    """
    Aborts a background task using a Soft-Revoke mechanism.
    Sets a cancellation flag in Redis that the worker checks periodically.
    """
    # 1. Standard Celery Revoke (Stops task if it hasn't started yet)
    celery_app.control.revoke(task_id)
    
    # 2. Redis Kill-Switch (Signals a running thread to stop itself)
    # We use the existing Redis backend client to set the flag
    try:
        celery_app.backend.client.set(f"cancelled:{task_id}", "true", ex=3600)
    except Exception as e:
        print(f"Warning: Could not set Redis kill-switch: {e}")

    return TaskResponse(
        task_id=task_id,
        status="REVOKED",
        message="Stop signal sent to the indexing engine."
    )

from app.services.history_service import HistoryManager

@router.post("/chat")
async def chat(data: ChatRequest):
    """
    Answers a question by streaming tokens from the LLM in real-time.
    Supports session-based memory and context-aware retrieval.
    """
    # 1. Handle History Wipe (New Chat Start) 🧹
    if data.clear_history:
        HistoryManager.clear_session(data.session_id)
        
    return StreamingResponse(
        stream_answer(data.query, data.session_id, data.context_url),
        media_type="text/event-stream"
    )
