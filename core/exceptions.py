"""
Custom exceptions for IDM-VTON application.
Provides structured error handling with user-friendly messages.
"""

from typing import Optional, Dict, Any


class IDMVTONError(Exception):
    """Base exception for IDM-VTON application."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ModelError(IDMVTONError):
    """Exception raised for model-related errors."""
    
    def __init__(self, message: str, model_name: Optional[str] = None, **kwargs):
        self.model_name = model_name
        super().__init__(message, error_code="MODEL_ERROR", details={"model_name": model_name, **kwargs})


class ModelLoadError(ModelError):
    """Exception raised when model loading fails."""
    
    def __init__(self, model_name: str, reason: str, **kwargs):
        message = f"Failed to load model '{model_name}': {reason}"
        super().__init__(message, model_name=model_name, reason=reason, **kwargs)


class ModelInferenceError(ModelError):
    """Exception raised when model inference fails."""
    
    def __init__(self, model_name: str, reason: str, **kwargs):
        message = f"Inference failed for model '{model_name}': {reason}"
        super().__init__(message, model_name=model_name, reason=reason, **kwargs)


class PreprocessingError(IDMVTONError):
    """Exception raised for preprocessing errors."""
    
    def __init__(self, message: str, step: Optional[str] = None, **kwargs):
        self.step = step
        super().__init__(message, error_code="PREPROCESSING_ERROR", details={"step": step, **kwargs})


class ImageProcessingError(PreprocessingError):
    """Exception raised for image processing errors."""
    
    def __init__(self, operation: str, reason: str, **kwargs):
        message = f"Image processing failed during '{operation}': {reason}"
        super().__init__(message, step=operation, operation=operation, reason=reason, **kwargs)


class MaskGenerationError(PreprocessingError):
    """Exception raised for mask generation errors."""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Mask generation failed: {reason}"
        super().__init__(message, step="mask_generation", reason=reason, **kwargs)


class PoseEstimationError(PreprocessingError):
    """Exception raised for pose estimation errors."""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Pose estimation failed: {reason}"
        super().__init__(message, step="pose_estimation", reason=reason, **kwargs)


class ValidationError(IDMVTONError):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        self.field = field
        self.value = value
        super().__init__(message, error_code="VALIDATION_ERROR", details={"field": field, "value": value, **kwargs})


class OptimizationError(IDMVTONError):
    """Exception raised for optimization-related errors."""
    
    def __init__(self, message: str, optimization_type: Optional[str] = None, **kwargs):
        self.optimization_type = optimization_type
        super().__init__(message, error_code="OPTIMIZATION_ERROR", details={"optimization_type": optimization_type, **kwargs})


class ResourceLimitError(IDMVTONError):
    """Exception raised when resource limits are exceeded."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None, **kwargs):
        self.resource_type = resource_type
        super().__init__(message, error_code="RESOURCE_LIMIT_ERROR", details={"resource_type": resource_type, "details": details, **kwargs})


class ImageValidationError(ValidationError):
    """Exception raised for image validation errors."""
    
    def __init__(self, field: str, reason: str, **kwargs):
        message = f"Image validation failed for '{field}': {reason}"
        super().__init__(message, field=field, reason=reason, **kwargs)


class ParameterValidationError(ValidationError):
    """Exception raised for parameter validation errors."""
    
    def __init__(self, parameter: str, value: Any, reason: str, **kwargs):
        message = f"Parameter validation failed for '{parameter}' (value: {value}): {reason}"
        super().__init__(message, field=parameter, value=value, reason=reason, **kwargs)


class TaskError(IDMVTONError):
    """Exception raised for task-related errors."""
    
    def __init__(self, message: str, task_id: Optional[str] = None, **kwargs):
        self.task_id = task_id
        super().__init__(message, error_code="TASK_ERROR", details={"task_id": task_id, **kwargs})


class TaskNotFoundError(TaskError):
    """Exception raised when a task is not found."""
    
    def __init__(self, task_id: str):
        message = f"Task '{task_id}' not found"
        super().__init__(message, task_id=task_id)


class TaskProcessingError(TaskError):
    """Exception raised when task processing fails."""
    
    def __init__(self, task_id: str, reason: str, **kwargs):
        message = f"Task processing failed for '{task_id}': {reason}"
        super().__init__(message, task_id=task_id, reason=reason, **kwargs)


class ResourceError(IDMVTONError):
    """Exception raised for resource-related errors."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        self.resource_type = resource_type
        super().__init__(message, error_code="RESOURCE_ERROR", details={"resource_type": resource_type, **kwargs})


class MemoryError(ResourceError):
    """Exception raised for memory-related errors."""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Memory error: {reason}"
        super().__init__(message, resource_type="memory", reason=reason, **kwargs)


class GPUError(ResourceError):
    """Exception raised for GPU-related errors."""
    
    def __init__(self, reason: str, **kwargs):
        message = f"GPU error: {reason}"
        super().__init__(message, resource_type="gpu", reason=reason, **kwargs)


class ConfigurationError(IDMVTONError):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        self.config_key = config_key
        super().__init__(message, error_code="CONFIGURATION_ERROR", details={"config_key": config_key, **kwargs})


class ServiceError(IDMVTONError):
    """Exception raised for service-related errors."""
    
    def __init__(self, message: str, service_name: Optional[str] = None, **kwargs):
        self.service_name = service_name
        super().__init__(message, error_code="SERVICE_ERROR", details={"service_name": service_name, **kwargs})


class DatabaseError(ServiceError):
    """Exception raised for database-related errors."""
    
    def __init__(self, service_name: str, reason: str, **kwargs):
        message = f"Database error in '{service_name}': {reason}"
        super().__init__(message, service_name=service_name, reason=reason, **kwargs)


class RedisError(ServiceError):
    """Exception raised for Redis-related errors."""
    
    def __init__(self, reason: str, **kwargs):
        message = f"Redis error: {reason}"
        super().__init__(message, service_name="redis", reason=reason, **kwargs)


def create_user_friendly_error(exception: Exception) -> str:
    """Create a user-friendly error message from an exception."""
    if isinstance(exception, IDMVTONError):
        return exception.message
    
    # Handle common external exceptions
    if isinstance(exception, (ValueError, TypeError)):
        return f"Invalid input: {str(exception)}"
    elif isinstance(exception, FileNotFoundError):
        return f"File not found: {str(exception)}"
    elif isinstance(exception, PermissionError):
        return f"Permission denied: {str(exception)}"
    elif isinstance(exception, MemoryError):
        return "Insufficient memory to process the request"
    elif isinstance(exception, RuntimeError):
        return f"Runtime error: {str(exception)}"
    else:
        return f"An unexpected error occurred: {str(exception)}"


def get_error_response(exception: Exception) -> Dict[str, Any]:
    """Get a structured error response from an exception."""
    if isinstance(exception, IDMVTONError):
        return {
            "error": exception.error_code or "IDMVTON_ERROR",
            "message": exception.message,
            "details": exception.details
        }
    else:
        return {
            "error": "UNKNOWN_ERROR",
            "message": create_user_friendly_error(exception),
            "details": {"exception_type": type(exception).__name__}
        }
