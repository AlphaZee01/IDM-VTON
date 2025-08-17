"""
Task service for IDM-VTON.
Handles task management, background processing, and result storage.
"""

import time
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
import torch
from PIL import Image
import structlog
from functools import lru_cache
import redis.asyncio as redis

from config import settings
from services.model_service import get_model_service
from services.preprocessing_service import get_preprocessing_service
from api.models import TaskStatus

logger = structlog.get_logger()


class TaskService:
    """Service for managing try-on tasks and background processing."""
    
    def __init__(self):
        self.redis_client = None
        self.tasks_dir = Path(settings.data_path) / "tasks"
        self.results_dir = Path(settings.data_path) / "results"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Initialize task service and Redis connection."""
        try:
            logger.info("Initializing task service")
            
            # Initialize Redis connection
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Redis connection established")
            
            # Start background task processor
            asyncio.create_task(self._process_tasks())
            
            logger.info("Task service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize task service", error=str(e), exc_info=True)
            raise
    
    async def submit_task(self, task_data: Dict[str, Any]) -> str:
        """Submit a new task for processing."""
        try:
            task_id = task_data["task_id"]
            
            # Save task data to Redis
            task_key = f"task:{task_id}"
            await self.redis_client.hset(task_key, mapping={
                "status": TaskStatus.PENDING,
                "created_at": task_data["created_at"],
                "parameters": json.dumps(task_data["parameters"]),
                "garment_description": task_data["garment_description"]
            })
            
            # Add to processing queue
            await self.redis_client.lpush("task_queue", task_id)
            
            logger.info("Task submitted", task_id=task_id)
            return task_id
            
        except Exception as e:
            logger.error("Failed to submit task", error=str(e), exc_info=True)
            raise
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task."""
        try:
            task_key = f"task:{task_id}"
            task_data = await self.redis_client.hgetall(task_key)
            
            if not task_data:
                return None
            
            # Get result paths if task is completed
            result_url = None
            mask_url = None
            if task_data.get("status") == TaskStatus.COMPLETED:
                result_path = self.results_dir / f"{task_id}_result.png"
                mask_path = self.results_dir / f"{task_id}_mask.png"
                
                if result_path.exists():
                    result_url = f"/api/v1/tryon/{task_id}/result"
                if mask_path.exists():
                    mask_url = f"/api/v1/tryon/{task_id}/mask"
            
            return {
                "task_id": task_id,
                "status": task_data.get("status", TaskStatus.PENDING),
                "progress": float(task_data.get("progress", 0)),
                "result_url": result_url,
                "mask_url": mask_url,
                "error_message": task_data.get("error_message"),
                "created_at": task_data.get("created_at"),
                "completed_at": task_data.get("completed_at"),
                "processing_time": task_data.get("processing_time")
            }
            
        except Exception as e:
            logger.error("Failed to get task status", task_id=task_id, error=str(e), exc_info=True)
            return None
    
    async def get_result_path(self, task_id: str) -> Optional[Path]:
        """Get the path to the result image."""
        try:
            result_path = self.results_dir / f"{task_id}_result.png"
            return result_path if result_path.exists() else None
        except Exception as e:
            logger.error("Failed to get result path", task_id=task_id, error=str(e))
            return None
    
    async def get_mask_path(self, task_id: str) -> Optional[Path]:
        """Get the path to the mask image."""
        try:
            mask_path = self.results_dir / f"{task_id}_mask.png"
            return mask_path if mask_path.exists() else None
        except Exception as e:
            logger.error("Failed to get mask path", task_id=task_id, error=str(e))
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task."""
        try:
            task_key = f"task:{task_id}"
            status = await self.redis_client.hget(task_key, "status")
            
            if status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                await self.redis_client.hset(task_key, "status", TaskStatus.FAILED)
                await self.redis_client.hset(task_key, "error_message", "Task cancelled by user")
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to cancel task", task_id=task_id, error=str(e), exc_info=True)
            return False
    
    async def list_tasks(
        self, 
        status: Optional[str] = None, 
        limit: int = 10, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List tasks with optional filtering."""
        try:
            # Get all task keys
            task_keys = await self.redis_client.keys("task:*")
            tasks = []
            
            for key in task_keys[offset:offset + limit]:
                task_id = key.split(":")[1]
                task_data = await self.redis_client.hgetall(key)
                
                if status and task_data.get("status") != status:
                    continue
                
                tasks.append({
                    "task_id": task_id,
                    "status": task_data.get("status", TaskStatus.PENDING),
                    "created_at": task_data.get("created_at"),
                    "garment_description": task_data.get("garment_description", "")
                })
            
            return tasks
            
        except Exception as e:
            logger.error("Failed to list tasks", error=str(e), exc_info=True)
            return []
    
    async def _process_tasks(self):
        """Background task processor."""
        logger.info("Starting background task processor")
        
        while True:
            try:
                # Wait for task from queue
                task_id = await self.redis_client.brpop("task_queue", timeout=1)
                
                if task_id:
                    task_id = task_id[1]  # Redis returns (key, value) tuple
                    await self._process_single_task(task_id)
                
            except Exception as e:
                logger.error("Error in task processor", error=str(e), exc_info=True)
                await asyncio.sleep(1)
    
    async def _process_single_task(self, task_id: str):
        """Process a single task."""
        try:
            task_key = f"task:{task_id}"
            
            # Update status to processing
            await self.redis_client.hset(task_key, "status", TaskStatus.PROCESSING)
            await self.redis_client.hset(task_key, "progress", 10)
            
            logger.info("Processing task", task_id=task_id)
            
            # Get task data
            task_data = await self.redis_client.hgetall(task_key)
            parameters = json.loads(task_data.get("parameters", "{}"))
            garment_description = task_data.get("garment_description", "")
            
            # Update progress
            await self.redis_client.hset(task_key, "progress", 20)
            
            # Get services
            model_service = get_model_service()
            preprocessing_service = get_preprocessing_service()
            
            # Initialize services if needed
            if not model_service.models_loaded:
                await model_service.initialize()
            
            await self.redis_client.hset(task_key, "progress", 30)
            
            # TODO: Get uploaded images from storage
            # For now, we'll use placeholder images
            # In production, you'd get the actual uploaded images
            
            # Preprocess images
            # human_image = await self._get_uploaded_image(task_id, "human")
            # garment_image = await self._get_uploaded_image(task_id, "garment")
            
            # For now, create dummy images
            human_image = Image.new('RGB', (settings.image_width, settings.image_height), (128, 128, 128))
            garment_image = Image.new('RGB', (settings.image_width, settings.image_height), (255, 255, 255))
            
            await self.redis_client.hset(task_key, "progress", 50)
            
            # Preprocess images
            preprocessed = await preprocessing_service.preprocess_images(
                human_image=human_image,
                garment_image=garment_image,
                auto_mask=parameters.get('auto_mask', True),
                auto_crop=parameters.get('auto_crop', False)
            )
            
            await self.redis_client.hset(task_key, "progress", 70)
            
            # Run inference
            result_images = await model_service.run_inference(
                human_image=preprocessed["human_tensor"],
                garment_image=preprocessed["garment_tensor"],
                garment_description=garment_description,
                mask_image=preprocessed["mask_tensor"],
                pose_image=preprocessed["pose_tensor"],
                parameters=parameters
            )
            
            await self.redis_client.hset(task_key, "progress", 90)
            
            # Save results
            await self._save_results(task_id, result_images, preprocessed["mask_image"])
            
            # Update task status
            completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
            processing_time = time.time() - float(task_data.get("created_at_timestamp", time.time()))
            
            await self.redis_client.hset(task_key, mapping={
                "status": TaskStatus.COMPLETED,
                "progress": 100,
                "completed_at": completed_at,
                "processing_time": processing_time
            })
            
            logger.info("Task completed successfully", task_id=task_id)
            
        except Exception as e:
            logger.error("Task processing failed", task_id=task_id, error=str(e), exc_info=True)
            
            # Update task status to failed
            await self.redis_client.hset(task_key, mapping={
                "status": TaskStatus.FAILED,
                "error_message": str(e)
            })
    
    async def _save_results(self, task_id: str, result_images: torch.Tensor, mask_image: Image.Image):
        """Save task results to disk."""
        try:
            # Convert result tensor to PIL image
            result_tensor = result_images[0]  # Get first image
            result_tensor = (result_tensor + 1.0) / 2.0  # Denormalize
            result_tensor = torch.clamp(result_tensor, 0, 1)
            
            result_image = transforms.ToPILImage()(result_tensor)
            
            # Save result image
            result_path = self.results_dir / f"{task_id}_result.png"
            result_image.save(result_path, "PNG")
            
            # Save mask image
            mask_path = self.results_dir / f"{task_id}_mask.png"
            mask_image.save(mask_path, "PNG")
            
            logger.info("Results saved", task_id=task_id)
            
        except Exception as e:
            logger.error("Failed to save results", task_id=task_id, error=str(e), exc_info=True)
            raise
    
    async def _get_uploaded_image(self, task_id: str, image_type: str) -> Image.Image:
        """Get uploaded image from storage."""
        # TODO: Implement image retrieval from storage
        # This would depend on your storage solution (local files, S3, etc.)
        raise NotImplementedError("Image storage not implemented yet")
    
    async def cleanup(self):
        """Clean up task service resources."""
        try:
            logger.info("Cleaning up task service")
            
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("Task service cleanup completed")
            
        except Exception as e:
            logger.error("Failed to cleanup task service", error=str(e), exc_info=True)


# Global task service instance
_task_service = None


@lru_cache(maxsize=1)
def get_task_service() -> TaskService:
    """Get the global task service instance."""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service


async def initialize_task_service():
    """Initialize the global task service."""
    service = get_task_service()
    await service.initialize()
    return service


async def cleanup_task_service():
    """Clean up the global task service."""
    global _task_service
    if _task_service is not None:
        await _task_service.cleanup()
        _task_service = None
