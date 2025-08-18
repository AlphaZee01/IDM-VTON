"""
Configuration management for IDM-VTON application.
Uses Pydantic settings for environment-based configuration.
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = "IDM-VTON"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # GPU settings
    cuda_visible_devices: str = Field(default="0", env="CUDA_VISIBLE_DEVICES")
    device: str = Field(default="cuda:0", env="DEVICE")
    
    # Model paths
    model_path: str = Field(default="/app/models", env="MODEL_PATH")
    ckpt_path: str = Field(default="/app/ckpt", env="CKPT_PATH")
    data_path: str = Field(default="/app/data", env="DATA_PATH")
    
    # Hugging Face model
    hf_model_name: str = Field(default="yisol/IDM-VTON", env="HF_MODEL_NAME")
    
    # Model configuration
    image_width: int = Field(default=768, env="IMAGE_WIDTH")
    image_height: int = Field(default=1024, env="IMAGE_HEIGHT")
    num_inference_steps: int = Field(default=30, env="NUM_INFERENCE_STEPS")
    guidance_scale: float = Field(default=2.0, env="GUIDANCE_SCALE")
    
    # Performance settings
    batch_size: int = Field(default=1, env="BATCH_SIZE")
    max_concurrent_requests: int = Field(default=5, env="MAX_CONCURRENT_REQUESTS")
    max_processing_time: int = Field(default=300, env="MAX_PROCESSING_TIME")  # 5 minutes
    max_memory_usage: int = Field(default=8192, env="MAX_MEMORY_USAGE")  # 8GB
    request_timeout: int = Field(default=300, env="REQUEST_TIMEOUT")  # 5 minutes
    
    # Redis settings (for caching and background tasks)
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    # Security settings
    api_key_header: str = Field(default="X-API-Key", env="API_KEY_HEADER")
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # File upload settings
    max_file_size: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    allowed_image_formats: List[str] = Field(
        default=["jpg", "jpeg", "png"], 
        env="ALLOWED_IMAGE_FORMATS"
    )
    
    # Logging settings
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    # Monitoring settings
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    @validator("allowed_origins", mode="before")
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("allowed_image_formats", mode="before")
    def parse_allowed_image_formats(cls, v):
        if isinstance(v, str):
            return [fmt.strip().lower() for fmt in v.split(",")]
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def validate_paths():
    """Validate that required paths exist and are accessible."""
    paths_to_check = [
        settings.model_path,
        settings.ckpt_path,
        settings.data_path
    ]
    
    for path in paths_to_check:
        path_obj = Path(path)
        if not path_obj.exists():
            path_obj.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {path}")
    
    return True


def get_model_paths():
    """Get model-specific paths."""
    return {
        "densepose": Path(settings.ckpt_path) / "densepose" / "model_final_162be9.pkl",
        "humanparsing": {
            "atr": Path(settings.ckpt_path) / "humanparsing" / "parsing_atr.onnx",
            "lip": Path(settings.ckpt_path) / "humanparsing" / "parsing_lip.onnx"
        },
        "openpose": Path(settings.ckpt_path) / "openpose" / "ckpts" / "body_pose_model.pth",
        "ip_adapter": Path(settings.ckpt_path) / "ip_adapter" / "ip-adapter-plus_sdxl_vit-h.bin",
        "image_encoder": Path(settings.ckpt_path) / "image_encoder"
    }


# Validate paths on import
validate_paths()
