"""
Resource management service for IDM-VTON.
Handles memory limits, processing time limits, and concurrent request limits.
"""

import time
import asyncio
import psutil
import torch
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
import structlog
from dataclasses import dataclass
from enum import Enum

from config import settings
from core.exceptions import ResourceLimitError

logger = structlog.get_logger()


class ResourceType(Enum):
    """Types of resources that can be monitored."""
    MEMORY = "memory"
    GPU_MEMORY = "gpu_memory"
    PROCESSING_TIME = "processing_time"
    CONCURRENT_REQUESTS = "concurrent_requests"
    CPU_USAGE = "cpu_usage"


@dataclass
class ResourceLimit:
    """Resource limit configuration."""
    resource_type: ResourceType
    limit: float
    warning_threshold: float = 0.8
    unit: str = ""


class ResourceMonitor:
    """Monitor system resources and enforce limits."""
    
    def __init__(self):
        self.device = settings.device
        self.active_requests = 0
        self.max_concurrent_requests = settings.max_concurrent_requests
        self.max_processing_time = settings.max_processing_time
        self.max_memory_usage = settings.max_memory_usage
        
        # Resource limits
        self.limits = {
            ResourceType.MEMORY: ResourceLimit(
                ResourceType.MEMORY,
                self.max_memory_usage,
                0.8,
                "MB"
            ),
            ResourceType.PROCESSING_TIME: ResourceLimit(
                ResourceType.PROCESSING_TIME,
                self.max_processing_time,
                0.9,
                "seconds"
            ),
            ResourceType.CONCURRENT_REQUESTS: ResourceLimit(
                ResourceType.CONCURRENT_REQUESTS,
                self.max_concurrent_requests,
                0.9,
                "requests"
            )
        }
        
        # Performance tracking
        self.performance_stats = {
            "total_requests": 0,
            "rejected_requests": 0,
            "average_processing_time": 0,
            "peak_memory_usage": 0,
            "peak_gpu_memory_usage": 0
        }
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss": memory_info.rss / 1024 / 1024,  # MB
                "vms": memory_info.vms / 1024 / 1024,  # MB
                "percent": process.memory_percent(),
                "available": psutil.virtual_memory().available / 1024 / 1024  # MB
            }
        except Exception as e:
            logger.error("Failed to get memory usage", error=str(e))
            return {"error": str(e)}
    
    def get_gpu_memory_usage(self) -> Dict[str, float]:
        """Get current GPU memory usage."""
        try:
            if torch.cuda.is_available():
                return {
                    "allocated": torch.cuda.memory_allocated() / 1024 / 1024,  # MB
                    "cached": torch.cuda.memory_reserved() / 1024 / 1024,  # MB
                    "max_allocated": torch.cuda.max_memory_allocated() / 1024 / 1024,  # MB
                    "device_count": torch.cuda.device_count()
                }
            else:
                return {"error": "CUDA not available"}
        except Exception as e:
            logger.error("Failed to get GPU memory usage", error=str(e))
            return {"error": str(e)}
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.error("Failed to get CPU usage", error=str(e))
            return 0.0
    
    def check_resource_availability(self) -> Dict[str, Any]:
        """Check if resources are available for processing."""
        try:
            memory_usage = self.get_memory_usage()
            gpu_memory_usage = self.get_gpu_memory_usage()
            cpu_usage = self.get_cpu_usage()
            
            # Check memory limit
            memory_available = memory_usage.get("rss", 0) < self.max_memory_usage
            
            # Check GPU memory limit (if available)
            gpu_memory_available = True
            if "error" not in gpu_memory_usage:
                gpu_allocated = gpu_memory_usage.get("allocated", 0)
                gpu_memory_available = gpu_allocated < (self.max_memory_usage * 0.8)  # 80% of system memory
            
            # Check concurrent requests limit
            concurrent_available = self.active_requests < self.max_concurrent_requests
            
            # Check CPU usage (warn if > 90%)
            cpu_available = cpu_usage < 90.0
            
            return {
                "available": all([memory_available, gpu_memory_available, concurrent_available, cpu_available]),
                "memory_available": memory_available,
                "gpu_memory_available": gpu_memory_available,
                "concurrent_available": concurrent_available,
                "cpu_available": cpu_available,
                "current_usage": {
                    "memory_mb": memory_usage.get("rss", 0),
                    "gpu_memory_mb": gpu_memory_usage.get("allocated", 0),
                    "concurrent_requests": self.active_requests,
                    "cpu_percent": cpu_usage
                },
                "limits": {
                    "memory_mb": self.max_memory_usage,
                    "concurrent_requests": self.max_concurrent_requests,
                    "processing_time_seconds": self.max_processing_time
                }
            }
            
        except Exception as e:
            logger.error("Failed to check resource availability", error=str(e))
            return {"available": False, "error": str(e)}
    
    @asynccontextmanager
    async def request_context(self, request_id: str):
        """Context manager for managing request resources."""
        start_time = time.time()
        
        try:
            # Check resource availability
            resource_status = self.check_resource_availability()
            if not resource_status.get("available", False):
                self.performance_stats["rejected_requests"] += 1
                raise ResourceLimitError(
                    "Insufficient resources available",
                    resource_type="system_resources",
                    details=resource_status
                )
            
            # Increment active requests
            self.active_requests += 1
            self.performance_stats["total_requests"] += 1
            
            logger.info(
                "Request started",
                request_id=request_id,
                active_requests=self.active_requests,
                resource_status=resource_status
            )
            
            yield resource_status
            
        except Exception as e:
            logger.error(
                "Request failed",
                request_id=request_id,
                error=str(e),
                processing_time=time.time() - start_time
            )
            raise
            
        finally:
            # Decrement active requests
            self.active_requests = max(0, self.active_requests - 1)
            
            # Update performance stats
            processing_time = time.time() - start_time
            self._update_performance_stats(processing_time)
            
            logger.info(
                "Request completed",
                request_id=request_id,
                active_requests=self.active_requests,
                processing_time=processing_time
            )
    
    def _update_performance_stats(self, processing_time: float):
        """Update performance statistics."""
        # Update average processing time
        total_requests = self.performance_stats["total_requests"]
        current_avg = self.performance_stats["average_processing_time"]
        self.performance_stats["average_processing_time"] = (
            (current_avg * (total_requests - 1) + processing_time) / total_requests
        )
        
        # Update peak memory usage
        memory_usage = self.get_memory_usage()
        current_memory = memory_usage.get("rss", 0)
        self.performance_stats["peak_memory_usage"] = max(
            self.performance_stats["peak_memory_usage"],
            current_memory
        )
        
        # Update peak GPU memory usage
        gpu_memory_usage = self.get_gpu_memory_usage()
        if "error" not in gpu_memory_usage:
            current_gpu_memory = gpu_memory_usage.get("allocated", 0)
            self.performance_stats["peak_gpu_memory_usage"] = max(
                self.performance_stats["peak_gpu_memory_usage"],
                current_gpu_memory
            )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        current_resources = self.check_resource_availability()
        
        return {
            **self.performance_stats,
            "current_resources": current_resources,
            "active_requests": self.active_requests,
            "resource_limits": {
                "max_memory_mb": self.max_memory_usage,
                "max_concurrent_requests": self.max_concurrent_requests,
                "max_processing_time_seconds": self.max_processing_time
            }
        }
    
    async def cleanup_resources(self):
        """Clean up resources and reset counters."""
        try:
            # Clear GPU cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Reset counters
            self.active_requests = 0
            
            logger.info("Resource cleanup completed")
            
        except Exception as e:
            logger.error("Resource cleanup failed", error=str(e))


class ResourceManager:
    """Main resource management service."""
    
    def __init__(self):
        self.monitor = ResourceMonitor()
        self._cleanup_task = None
    
    async def initialize(self):
        """Initialize the resource manager."""
        try:
            logger.info("Initializing resource manager")
            
            # Start periodic cleanup task
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            
            logger.info("Resource manager initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize resource manager", error=str(e))
            raise
    
    async def _periodic_cleanup(self):
        """Periodic resource cleanup task."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self.monitor.cleanup_resources()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Periodic cleanup failed", error=str(e))
    
    async def check_resources(self) -> Dict[str, Any]:
        """Check current resource availability."""
        return self.monitor.check_resource_availability()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current resource statistics."""
        return self.monitor.get_performance_stats()
    
    @asynccontextmanager
    async def request_context(self, request_id: str):
        """Get a resource context for a request."""
        async with self.monitor.request_context(request_id) as resources:
            yield resources
    
    async def shutdown(self):
        """Shutdown the resource manager."""
        try:
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            await self.monitor.cleanup_resources()
            logger.info("Resource manager shutdown completed")
            
        except Exception as e:
            logger.error("Resource manager shutdown failed", error=str(e))


# Global resource manager instance
_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


async def initialize_resource_manager():
    """Initialize the global resource manager."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
        await _resource_manager.initialize()
