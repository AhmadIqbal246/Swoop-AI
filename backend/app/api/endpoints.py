from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.core.celery_app import celery_app
from celery.result import AsyncResult
from app.services.llm_service import stream_answer
from app.schemas.request import ProcessURLRequest, ChatRequest
from app.schemas.response import TaskResponse, ChatResponse
from app.tasks.worker import process_url_task
from app.core.logging import app_logger as logger # Fix 1.4: Standardized Logging

router = APIRouter()

@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Retrieves the stored chat history for a given session.
    """
    from app.services.history_service import HistoryManager
    history = HistoryManager.get_history(session_id)
    return {"history": history}

@router.post("/process-url", response_model=TaskResponse)
async def process_url(data: ProcessURLRequest):
    """
    Submits a URL to be processed in the background.
    """
    task = process_url_task.delay(str(data.url))
    logger.info("URL process requested", extra={"url": data.url, "task_id": task.id})
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
    response = TaskResponse(task_id=task_id, status=result.status)
    
    if result.status == "SUCCESS":
        task_result = result.result or {}
        if task_result.get('status') == 'REVOKED':
            response.status = "REVOKED"
            response.message = task_result.get('message', 'Process stopped.')
        else:
            response.status = "COMPLETED"
            response.message = task_result.get('message', 'Indexing completed!')
        response.processed_pages = task_result.get('processed_pages', [])
    elif result.status == "FAILURE":
        logger.error("Task failure recorded", extra={"task_id": task_id, "error": str(result.result)}) # Fix 7.2
        response.status = "FAILURE"
        response.message = "Process failed."
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
    """
    celery_app.control.revoke(task_id)
    try:
        # Fix 5.1: Graceful failure if Redis is down
        from app.services.history_service import HistoryManager
        HistoryManager.redis_client.set(f"cancelled:{task_id}", "true", ex=3600)
    except Exception:
        logger.error("Failed to set Redis cancel-switch", exc_info=True)
        return {"error": "History service unavailable. Cannot stop task reliably."}

    logger.warning("Stop signal sent to task", extra={"task_id": task_id})
    return TaskResponse(
        task_id=task_id,
        status="REVOKED",
        message="Stop signal sent to the indexing engine."
    )

@router.post("/chat")
async def chat(data: ChatRequest):
    """
    Answers a question by streaming tokens from the LLM in real-time.
    """
    from app.services.history_service import HistoryManager
    if data.clear_history:
        HistoryManager.clear_session(data.session_id)
        
    return StreamingResponse(
        stream_answer(data.query, data.session_id, data.context_url),
        media_type="text/event-stream"
    )
