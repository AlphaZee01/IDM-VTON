"""
API routes for IDM-VTON.
"""

import time
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
import structlog

from config import settings
from api.models import (
    TryOnRequest, TryOnResponse, TaskStatusResponse, ModelStatusResponse,
    generate_task_id, create_error_response
)
from services.model_service import get_model_service
from services.task_service import get_task_service

logger = structlog.get_logger()

router = APIRouter()


@router.get("/status", response_model=ModelStatusResponse)
async def get_model_status():
    """Get model status and health information."""
    try:
        model_service = get_model_service()
        status = await model_service.get_status()
        return ModelStatusResponse(**status)
    except Exception as e:
        logger.error("Failed to get model status", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get model status")


@router.post("/tryon", response_model=TryOnResponse)
async def create_tryon_task(
    human_image: UploadFile = File(..., description="Human image"),
    garment_image: UploadFile = File(..., description="Garment image"),
    garment_description: str = Form(..., description="Description of the garment"),
    request_data: TryOnRequest = Depends()
):
    """Create a new virtual try-on task."""
    
    # Validate file types
    allowed_formats = settings.allowed_image_formats
    human_ext = human_image.filename.split('.')[-1].lower() if human_image.filename else ''
    garment_ext = garment_image.filename.split('.')[-1].lower() if garment_image.filename else ''
    
    if human_ext not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Human image must be one of: {', '.join(allowed_formats)}"
        )
    
    if garment_ext not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Garment image must be one of: {', '.join(allowed_formats)}"
        )
    
    # Validate file sizes
    if human_image.size and human_image.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Human image too large. Maximum size: {settings.max_file_size} bytes"
        )
    
    if garment_image.size and garment_image.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Garment image too large. Maximum size: {settings.max_file_size} bytes"
        )
    
    try:
        # Generate task ID
        task_id = generate_task_id()
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get task service
        task_service = get_task_service()
        
        # Create task
        task_data = {
            "task_id": task_id,
            "status": "pending",
            "human_image": human_image,
            "garment_image": garment_image,
            "garment_description": garment_description,
            "parameters": request_data.dict(),
            "created_at": created_at
        }
        
        # Submit task for processing
        await task_service.submit_task(task_data)
        
        logger.info(
            "Try-on task created",
            task_id=task_id,
            garment_description=garment_description
        )
        
        return TryOnResponse(
            task_id=task_id,
            status="pending",
            created_at=created_at
        )
        
    except Exception as e:
        logger.error(
            "Failed to create try-on task",
            error=str(e),
            garment_description=garment_description,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create try-on task"
        )


@router.get("/tryon/{task_id}", response_model=TaskStatusResponse)
async def get_tryon_status(task_id: str):
    """Get the status of a try-on task."""
    try:
        task_service = get_task_service()
        task_status = await task_service.get_task_status(task_id)
        
        if not task_status:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        return TaskStatusResponse(**task_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get task status",
            task_id=task_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get task status"
        )


@router.get("/tryon/{task_id}/result")
async def download_result(task_id: str):
    """Download the result image for a completed task."""
    try:
        task_service = get_task_service()
        result_path = await task_service.get_result_path(task_id)
        
        if not result_path:
            raise HTTPException(
                status_code=404,
                detail=f"Result for task {task_id} not found or not ready"
            )
        
        return FileResponse(
            result_path,
            media_type="image/png",
            filename=f"tryon_result_{task_id}.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to download result",
            task_id=task_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to download result"
        )


@router.get("/tryon/{task_id}/mask")
async def download_mask(task_id: str):
    """Download the mask image for a completed task."""
    try:
        task_service = get_task_service()
        mask_path = await task_service.get_mask_path(task_id)
        
        if not mask_path:
            raise HTTPException(
                status_code=404,
                detail=f"Mask for task {task_id} not found or not ready"
            )
        
        return FileResponse(
            mask_path,
            media_type="image/png",
            filename=f"tryon_mask_{task_id}.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to download mask",
            task_id=task_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to download mask"
        )


@router.delete("/tryon/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or processing task."""
    try:
        task_service = get_task_service()
        success = await task_service.cancel_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found or cannot be cancelled"
            )
        
        logger.info("Task cancelled", task_id=task_id)
        
        return {"message": f"Task {task_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to cancel task",
            task_id=task_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel task"
        )


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
):
    """List tasks with optional filtering."""
    try:
        task_service = get_task_service()
        tasks = await task_service.list_tasks(
            status=status,
            limit=limit,
            offset=offset
        )
        
        return {
            "tasks": tasks,
            "total": len(tasks),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(
            "Failed to list tasks",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to list tasks"
        )


@router.get("/metrics")
async def get_metrics():
    """Get Prometheus metrics."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response
        
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get metrics"
        )
