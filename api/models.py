"""
Pydantic models for IDM-VTON API.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageFormat(str, Enum):
    """Supported image formats."""
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"


class TryOnRequest(BaseModel):
    """Request model for virtual try-on."""
    
    # Optional parameters
    num_inference_steps: int = Field(
        default=30,
        ge=20,
        le=50,
        description="Number of denoising steps"
    )
    guidance_scale: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Guidance scale for generation"
    )
    seed: Optional[int] = Field(
        default=None,
        ge=-1,
        le=2147483647,
        description="Random seed for reproducible results"
    )
    auto_mask: bool = Field(
        default=True,
        description="Use automatic mask generation"
    )
    auto_crop: bool = Field(
        default=False,
        description="Use automatic cropping and resizing"
    )
    
    @validator('num_inference_steps')
    def validate_inference_steps(cls, v):
        if v < 20 or v > 50:
            raise ValueError('num_inference_steps must be between 20 and 50')
        return v
    
    @validator('guidance_scale')
    def validate_guidance_scale(cls, v):
        if v < 1.0 or v > 10.0:
            raise ValueError('guidance_scale must be between 1.0 and 10.0')
        return v


class TryOnResponse(BaseModel):
    """Response model for virtual try-on."""
    
    task_id: str = Field(description="Unique task identifier")
    status: TaskStatus = Field(description="Current task status")
    result_url: Optional[str] = Field(
        default=None,
        description="URL to download the result image"
    )
    mask_url: Optional[str] = Field(
        default=None,
        description="URL to download the mask image"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )
    created_at: str = Field(description="Task creation timestamp")
    completed_at: Optional[str] = Field(
        default=None,
        description="Task completion timestamp"
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds"
    )


class TaskStatusResponse(BaseModel):
    """Response model for task status check."""
    
    task_id: str = Field(description="Unique task identifier")
    status: TaskStatus = Field(description="Current task status")
    progress: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Progress percentage (0-100)"
    )
    result_url: Optional[str] = Field(
        default=None,
        description="URL to download the result image"
    )
    mask_url: Optional[str] = Field(
        default=None,
        description="URL to download the mask image"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )
    created_at: str = Field(description="Task creation timestamp")
    completed_at: Optional[str] = Field(
        default=None,
        description="Task completion timestamp"
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds"
    )


class ModelStatusResponse(BaseModel):
    """Response model for model status."""
    
    model_loaded: bool = Field(description="Whether the model is loaded")
    device: str = Field(description="Device where model is loaded")
    memory_usage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Memory usage information"
    )
    model_size: Optional[str] = Field(
        default=None,
        description="Model size in human readable format"
    )
    last_loaded: Optional[str] = Field(
        default=None,
        description="Last model load timestamp"
    )


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(description="Service status")
    timestamp: float = Field(description="Current timestamp")
    version: str = Field(description="API version")
    service: str = Field(description="Service name")
    uptime: Optional[float] = Field(
        default=None,
        description="Service uptime in seconds"
    )
    memory_usage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Memory usage information"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    request_id: str = Field(description="Request identifier")
    status_code: int = Field(description="HTTP status code")
    timestamp: str = Field(description="Error timestamp")


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    
    error: str = Field(default="Validation error")
    message: str = Field(description="Validation error message")
    details: List[Dict[str, Any]] = Field(description="Validation error details")
    request_id: str = Field(description="Request identifier")
    status_code: int = Field(default=422)


class RateLimitResponse(BaseModel):
    """Rate limit error response model."""
    
    error: str = Field(default="Rate limit exceeded")
    message: str = Field(description="Rate limit message")
    retry_after: int = Field(description="Seconds to wait before retry")
    request_id: str = Field(description="Request identifier")
    status_code: int = Field(default=429)


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())


def create_error_response(
    error_type: str,
    message: str,
    request_id: str,
    status_code: int = 500,
    details: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Create a standardized error response."""
    response = {
        "error": error_type,
        "message": message,
        "request_id": request_id,
        "status_code": status_code,
        "timestamp": str(uuid.uuid4())  # Using UUID as timestamp for now
    }
    
    if details:
        response["details"] = details
    
    return response
