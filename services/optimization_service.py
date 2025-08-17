"""
Optimization service for IDM-VTON.
Handles model optimization, caching, and performance improvements.
"""

import time
import asyncio
import hashlib
import json
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import torch
import torch.nn as nn
from torch.ao.quantization import quantize_dynamic
import numpy as np
from PIL import Image
import structlog
from functools import lru_cache
import redis.asyncio as redis

from config import settings
from core.exceptions import OptimizationError

logger = structlog.get_logger()


class OptimizationService:
    """Service for model optimization and performance improvements."""
    
    def __init__(self):
        self.device = settings.device
        self.cache_dir = Path(settings.data_path) / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # Redis client for distributed caching
        self.redis_client = None
        if settings.redis_url:
            self.redis_client = redis.from_url(settings.redis_url)
        
        # Cache settings
        self.cache_ttl = 3600  # 1 hour
        self.max_cache_size = 1000  # Maximum cached items
        
        # Performance metrics
        self.performance_metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "quantization_time": 0,
            "batch_processing_time": 0
        }
    
    async def initialize(self):
        """Initialize the optimization service."""
        try:
            logger.info("Initializing optimization service")
            
            # Test Redis connection
            if self.redis_client:
                await self.redis_client.ping()
                logger.info("Redis connection established")
            
            # Create cache directories
            (self.cache_dir / "results").mkdir(exist_ok=True)
            (self.cache_dir / "preprocessed").mkdir(exist_ok=True)
            
            logger.info("Optimization service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize optimization service", error=str(e), exc_info=True)
            raise OptimizationError(f"Failed to initialize optimization service: {str(e)}")
    
    def quantize_model(self, model: nn.Module) -> nn.Module:
        """Apply dynamic quantization to reduce model size and improve inference speed."""
        try:
            start_time = time.time()
            
            # Apply dynamic quantization
            quantized_model = quantize_dynamic(
                model, 
                {nn.Linear, nn.Conv2d, nn.ConvTranspose2d}, 
                dtype=torch.qint8
            )
            
            quantization_time = time.time() - start_time
            self.performance_metrics["quantization_time"] += quantization_time
            
            logger.info(
                "Model quantization completed",
                quantization_time=quantization_time,
                original_size=self._get_model_size(model),
                quantized_size=self._get_model_size(quantized_model)
            )
            
            return quantized_model
            
        except Exception as e:
            logger.error("Model quantization failed", error=str(e), exc_info=True)
            raise OptimizationError(f"Model quantization failed: {str(e)}")
    
    def _get_model_size(self, model: nn.Module) -> int:
        """Get model size in MB."""
        param_size = 0
        buffer_size = 0
        
        for param in model.parameters():
            param_size += param.nelement() * param.element_size()
        
        for buffer in model.buffers():
            buffer_size += buffer.nelement() * buffer.element_size()
        
        size_mb = (param_size + buffer_size) / 1024 / 1024
        return size_mb
    
    def optimize_memory_usage(self, model: nn.Module) -> nn.Module:
        """Optimize memory usage by using mixed precision and gradient checkpointing."""
        try:
            # Enable gradient checkpointing to save memory
            if hasattr(model, 'gradient_checkpointing_enable'):
                model.gradient_checkpointing_enable()
            
            # Use mixed precision if available
            if torch.cuda.is_available():
                model = model.half()  # Use FP16
            
            logger.info("Memory optimization applied to model")
            return model
            
        except Exception as e:
            logger.error("Memory optimization failed", error=str(e), exc_info=True)
            raise OptimizationError(f"Memory optimization failed: {str(e)}")
    
    def generate_cache_key(self, human_image: Image.Image, garment_image: Image.Image, parameters: Dict[str, Any]) -> str:
        """Generate a unique cache key for the input combination."""
        try:
            # Create a hash of the images and parameters
            image_hash = hashlib.md5()
            
            # Add human image hash
            human_array = np.array(human_image)
            image_hash.update(human_array.tobytes())
            
            # Add garment image hash
            garment_array = np.array(garment_image)
            image_hash.update(garment_array.tobytes())
            
            # Add parameters hash
            params_str = json.dumps(parameters, sort_keys=True)
            image_hash.update(params_str.encode())
            
            return f"tryon_{image_hash.hexdigest()}"
            
        except Exception as e:
            logger.error("Cache key generation failed", error=str(e), exc_info=True)
            raise OptimizationError(f"Cache key generation failed: {str(e)}")
    
    async def get_cached_result(self, cache_key: str) -> Optional[str]:
        """Get cached result if available."""
        try:
            if not self.redis_client:
                return None
            
            # Try Redis cache first
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                self.performance_metrics["cache_hits"] += 1
                result_path = json.loads(cached_data)["result_path"]
                
                # Verify file exists
                if Path(result_path).exists():
                    logger.info("Cache hit", cache_key=cache_key)
                    return result_path
            
            # Try file system cache
            cache_file = self.cache_dir / "results" / f"{cache_key}.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                result_path = cached_data["result_path"]
                if Path(result_path).exists():
                    self.performance_metrics["cache_hits"] += 1
                    logger.info("File system cache hit", cache_key=cache_key)
                    return result_path
            
            self.performance_metrics["cache_misses"] += 1
            return None
            
        except Exception as e:
            logger.error("Cache retrieval failed", error=str(e), exc_info=True)
            return None
    
    async def cache_result(self, cache_key: str, result_path: str, metadata: Dict[str, Any] = None):
        """Cache the result for future use."""
        try:
            cache_data = {
                "result_path": result_path,
                "created_at": time.time(),
                "metadata": metadata or {}
            }
            
            # Cache in Redis
            if self.redis_client:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(cache_data)
                )
            
            # Cache in file system
            cache_file = self.cache_dir / "results" / f"{cache_key}.json"
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            logger.info("Result cached", cache_key=cache_key)
            
        except Exception as e:
            logger.error("Caching failed", error=str(e), exc_info=True)
    
    async def batch_process(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process multiple try-on tasks in batch for better efficiency."""
        try:
            start_time = time.time()
            
            if not tasks:
                return []
            
            # Group tasks by similar parameters for batch processing
            batched_tasks = self._group_tasks_by_parameters(tasks)
            results = []
            
            for batch in batched_tasks:
                batch_results = await self._process_batch(batch)
                results.extend(batch_results)
            
            batch_time = time.time() - start_time
            self.performance_metrics["batch_processing_time"] += batch_time
            
            logger.info(
                "Batch processing completed",
                total_tasks=len(tasks),
                batch_time=batch_time,
                average_time_per_task=batch_time / len(tasks)
            )
            
            return results
            
        except Exception as e:
            logger.error("Batch processing failed", error=str(e), exc_info=True)
            raise OptimizationError(f"Batch processing failed: {str(e)}")
    
    def _group_tasks_by_parameters(self, tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group tasks by similar parameters for efficient batch processing."""
        parameter_groups = {}
        
        for task in tasks:
            # Create a key based on parameters
            params = task.get('parameters', {})
            param_key = (
                params.get('num_inference_steps', 30),
                params.get('guidance_scale', 2.0),
                params.get('auto_mask', True),
                params.get('auto_crop', False)
            )
            
            if param_key not in parameter_groups:
                parameter_groups[param_key] = []
            parameter_groups[param_key].append(task)
        
        return list(parameter_groups.values())
    
    async def _process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of tasks with similar parameters."""
        # This would integrate with the model service for actual batch processing
        # For now, we'll process them sequentially but with optimized parameters
        
        results = []
        for task in batch:
            # Process individual task (placeholder for batch processing)
            result = await self._process_single_task(task)
            results.append(result)
        
        return results
    
    async def _process_single_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single task (placeholder for batch processing integration)."""
        # This would be integrated with the actual model service
        # For now, return a placeholder result
        return {
            "task_id": task.get("task_id"),
            "status": "completed",
            "result_path": task.get("result_path")
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        cache_hit_rate = 0
        total_requests = self.performance_metrics["cache_hits"] + self.performance_metrics["cache_misses"]
        
        if total_requests > 0:
            cache_hit_rate = self.performance_metrics["cache_hits"] / total_requests
        
        return {
            **self.performance_metrics,
            "cache_hit_rate": cache_hit_rate,
            "total_requests": total_requests,
            "cache_size": len(list(self.cache_dir.glob("*.json"))) if self.cache_dir.exists() else 0
        }
    
    async def cleanup_cache(self, max_age_hours: int = 24):
        """Clean up old cache entries."""
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            cleaned_count = 0
            
            # Clean file system cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    
                    if cache_data.get("created_at", 0) < cutoff_time:
                        cache_file.unlink()
                        cleaned_count += 1
                        
                        # Also remove the result file if it exists
                        result_path = cache_data.get("result_path")
                        if result_path and Path(result_path).exists():
                            Path(result_path).unlink()
                            
                except Exception as e:
                    logger.warning("Failed to clean cache file", file=str(cache_file), error=str(e))
            
            # Clean Redis cache (TTL handles this automatically)
            logger.info("Cache cleanup completed", cleaned_count=cleaned_count)
            
        except Exception as e:
            logger.error("Cache cleanup failed", error=str(e), exc_info=True)


# Global optimization service instance
_optimization_service = None


def get_optimization_service() -> OptimizationService:
    """Get the global optimization service instance."""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = OptimizationService()
    return _optimization_service


async def initialize_optimization_service():
    """Initialize the global optimization service."""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = OptimizationService()
        await _optimization_service.initialize()
