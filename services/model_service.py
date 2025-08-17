"""
Model service for IDM-VTON.
Handles model loading, caching, and inference pipeline management.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import torch
import structlog
from functools import lru_cache

from config import settings, get_model_paths
from api.middleware import MODEL_INFERENCE_DURATION, MODEL_INFERENCE_COUNT

logger = structlog.get_logger()


class ModelService:
    """Service for managing IDM-VTON models and inference."""
    
    def __init__(self):
        self.models_loaded = False
        self.device = settings.device
        self.model_paths = get_model_paths()
        self.last_loaded = None
        self._models = {}
        self._pipeline = None
        
    async def initialize(self):
        """Initialize and load all required models."""
        try:
            logger.info("Initializing model service", device=self.device)
            
            # Check CUDA availability
            if not torch.cuda.is_available() and self.device.startswith('cuda'):
                logger.warning("CUDA not available, falling back to CPU")
                self.device = 'cpu'
            
            # Load models asynchronously
            await self._load_models()
            
            self.models_loaded = True
            self.last_loaded = time.strftime("%Y-%m-%d %H:%M:%S")
            
            logger.info("Model service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize model service", error=str(e), exc_info=True)
            raise
    
    async def _load_models(self):
        """Load all required models."""
        # Import here to avoid circular imports
        from transformers import (
            CLIPImageProcessor,
            CLIPVisionModelWithProjection,
            CLIPTextModel,
            CLIPTextModelWithProjection,
            AutoTokenizer
        )
        from diffusers import DDPMScheduler, AutoencoderKL
        from src.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
        from src.unet_hacked_tryon import UNet2DConditionModel
        from src.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline
        
        logger.info("Loading IDM-VTON models")
        
        # Load main model components
        base_path = settings.hf_model_name
        
        # Load UNet models
        self._models['unet'] = UNet2DConditionModel.from_pretrained(
            base_path,
            subfolder="unet",
            torch_dtype=torch.float16,
        )
        
        self._models['unet_encoder'] = UNet2DConditionModel_ref.from_pretrained(
            base_path,
            subfolder="unet_encoder",
            torch_dtype=torch.float16,
        )
        
        # Load tokenizers
        self._models['tokenizer_one'] = AutoTokenizer.from_pretrained(
            base_path,
            subfolder="tokenizer",
            revision=None,
            use_fast=False,
        )
        
        self._models['tokenizer_two'] = AutoTokenizer.from_pretrained(
            base_path,
            subfolder="tokenizer_2",
            revision=None,
            use_fast=False,
        )
        
        # Load text encoders
        self._models['text_encoder_one'] = CLIPTextModel.from_pretrained(
            base_path,
            subfolder="text_encoder",
            torch_dtype=torch.float16,
        )
        
        self._models['text_encoder_two'] = CLIPTextModelWithProjection.from_pretrained(
            base_path,
            subfolder="text_encoder_2",
            torch_dtype=torch.float16,
        )
        
        # Load image encoder
        self._models['image_encoder'] = CLIPVisionModelWithProjection.from_pretrained(
            base_path,
            subfolder="image_encoder",
            torch_dtype=torch.float16,
        )
        
        # Load VAE and scheduler
        self._models['vae'] = AutoencoderKL.from_pretrained(
            base_path,
            subfolder="vae",
            torch_dtype=torch.float16,
        )
        
        self._models['scheduler'] = DDPMScheduler.from_pretrained(
            base_path, 
            subfolder="scheduler"
        )
        
        # Move models to device
        for name, model in self._models.items():
            if hasattr(model, 'to'):
                model.to(self.device)
                model.requires_grad_(False)
        
        # Create pipeline
        self._pipeline = TryonPipeline.from_pretrained(
            base_path,
            unet=self._models['unet'],
            vae=self._models['vae'],
            feature_extractor=CLIPImageProcessor(),
            text_encoder=self._models['text_encoder_one'],
            text_encoder_2=self._models['text_encoder_two'],
            tokenizer=self._models['tokenizer_one'],
            tokenizer_2=self._models['tokenizer_two'],
            scheduler=self._models['scheduler'],
            image_encoder=self._models['image_encoder'],
            torch_dtype=torch.float16,
        )
        
        self._pipeline.unet_encoder = self._models['unet_encoder']
        self._pipeline.to(self.device)
        
        logger.info("All models loaded successfully")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get model service status."""
        try:
            memory_usage = await self._get_memory_usage()
            
            return {
                "model_loaded": self.models_loaded,
                "device": self.device,
                "memory_usage": memory_usage,
                "model_size": await self._get_model_size(),
                "last_loaded": self.last_loaded
            }
        except Exception as e:
            logger.error("Failed to get model status", error=str(e), exc_info=True)
            return {
                "model_loaded": False,
                "device": self.device,
                "error": str(e)
            }
    
    async def _get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage."""
        try:
            if torch.cuda.is_available():
                return {
                    "gpu_allocated": torch.cuda.memory_allocated(),
                    "gpu_cached": torch.cuda.memory_reserved(),
                    "gpu_max_allocated": torch.cuda.max_memory_allocated(),
                    "gpu_device_count": torch.cuda.device_count()
                }
            else:
                return {"error": "CUDA not available"}
        except Exception as e:
            return {"error": f"Failed to get memory usage: {str(e)}"}
    
    async def _get_model_size(self) -> str:
        """Get total model size in human readable format."""
        try:
            total_params = 0
            for name, model in self._models.items():
                if hasattr(model, 'parameters'):
                    params = sum(p.numel() for p in model.parameters())
                    total_params += params
            
            # Convert to human readable format
            if total_params > 1e9:
                return f"{total_params / 1e9:.2f}B parameters"
            elif total_params > 1e6:
                return f"{total_params / 1e6:.2f}M parameters"
            elif total_params > 1e3:
                return f"{total_params / 1e3:.2f}K parameters"
            else:
                return f"{total_params} parameters"
        except Exception as e:
            return f"Error calculating model size: {str(e)}"
    
    async def warm_up(self):
        """Warm up the model with a dummy inference."""
        if not self.models_loaded:
            await self.initialize()
        
        try:
            logger.info("Warming up model with dummy inference")
            
            # Create dummy inputs
            dummy_human = torch.randn(1, 3, settings.image_height, settings.image_width).to(self.device)
            dummy_garment = torch.randn(1, 3, settings.image_height, settings.image_width).to(self.device)
            dummy_mask = torch.ones(1, 1, settings.image_height, settings.image_width).to(self.device)
            
            # Run dummy inference
            with torch.no_grad():
                with torch.cuda.amp.autocast():
                    _ = self._pipeline(
                        prompt_embeds=torch.randn(2, 77, 2048).to(self.device),
                        negative_prompt_embeds=torch.randn(2, 77, 2048).to(self.device),
                        pooled_prompt_embeds=torch.randn(2, 1280).to(self.device),
                        negative_pooled_prompt_embeds=torch.randn(2, 1280).to(self.device),
                        num_inference_steps=1,
                        strength=1.0,
                        pose_img=torch.randn(1, 3, settings.image_height, settings.image_width).to(self.device),
                        text_embeds_cloth=torch.randn(1, 77, 2048).to(self.device),
                        cloth=dummy_garment,
                        mask_image=dummy_mask,
                        image=dummy_human,
                        height=settings.image_height,
                        width=settings.image_width,
                        ip_adapter_image=dummy_garment,
                        guidance_scale=2.0,
                    )
            
            logger.info("Model warm-up completed")
            
        except Exception as e:
            logger.error("Failed to warm up model", error=str(e), exc_info=True)
            raise
    
    async def run_inference(
        self,
        human_image: torch.Tensor,
        garment_image: torch.Tensor,
        garment_description: str,
        mask_image: Optional[torch.Tensor] = None,
        pose_image: Optional[torch.Tensor] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> torch.Tensor:
        """Run virtual try-on inference."""
        if not self.models_loaded:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Set default parameters
            if parameters is None:
                parameters = {}
            
            num_inference_steps = parameters.get('num_inference_steps', settings.num_inference_steps)
            guidance_scale = parameters.get('guidance_scale', settings.guidance_scale)
            seed = parameters.get('seed', None)
            
            # Generate prompts
            prompt = f"model is wearing {garment_description}"
            negative_prompt = "monochrome, lowres, bad anatomy, worst quality, low quality"
            
            # Encode prompts
            with torch.no_grad():
                with torch.cuda.amp.autocast():
                    (
                        prompt_embeds,
                        negative_prompt_embeds,
                        pooled_prompt_embeds,
                        negative_pooled_prompt_embeds,
                    ) = self._pipeline.encode_prompt(
                        prompt,
                        num_images_per_prompt=1,
                        do_classifier_free_guidance=True,
                        negative_prompt=negative_prompt,
                    )
                    
                    cloth_prompt = f"a photo of {garment_description}"
                    (
                        prompt_embeds_c,
                        _,
                        _,
                        _,
                    ) = self._pipeline.encode_prompt(
                        cloth_prompt,
                        num_images_per_prompt=1,
                        do_classifier_free_guidance=False,
                        negative_prompt=negative_prompt,
                    )
            
            # Prepare inputs
            if mask_image is None:
                mask_image = torch.ones_like(human_image[:, :1, :, :])
            
            if pose_image is None:
                pose_image = human_image  # Use human image as fallback
            
            # Set generator for reproducibility
            generator = None
            if seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)
            
            # Run inference
            with torch.no_grad():
                with torch.cuda.amp.autocast():
                    images = self._pipeline(
                        prompt_embeds=prompt_embeds.to(self.device, torch.float16),
                        negative_prompt_embeds=negative_prompt_embeds.to(self.device, torch.float16),
                        pooled_prompt_embeds=pooled_prompt_embeds.to(self.device, torch.float16),
                        negative_pooled_prompt_embeds=negative_pooled_prompt_embeds.to(self.device, torch.float16),
                        num_inference_steps=num_inference_steps,
                        generator=generator,
                        strength=1.0,
                        pose_img=pose_image.to(self.device, torch.float16),
                        text_embeds_cloth=prompt_embeds_c.to(self.device, torch.float16),
                        cloth=garment_image.to(self.device, torch.float16),
                        mask_image=mask_image,
                        image=human_image,
                        height=settings.image_height,
                        width=settings.image_width,
                        ip_adapter_image=garment_image,
                        guidance_scale=guidance_scale,
                    )[0]
            
            # Record metrics
            duration = time.time() - start_time
            MODEL_INFERENCE_DURATION.labels(model_name="idm-vton").observe(duration)
            MODEL_INFERENCE_COUNT.labels(model_name="idm-vton", status="success").inc()
            
            logger.info(
                "Inference completed successfully",
                duration=duration,
                steps=num_inference_steps,
                guidance_scale=guidance_scale
            )
            
            return images
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            MODEL_INFERENCE_DURATION.labels(model_name="idm-vton").observe(duration)
            MODEL_INFERENCE_COUNT.labels(model_name="idm-vton", status="error").inc()
            
            logger.error(
                "Inference failed",
                error=str(e),
                duration=duration,
                exc_info=True
            )
            raise
    
    async def cleanup(self):
        """Clean up model resources."""
        try:
            logger.info("Cleaning up model resources")
            
            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Clear models
            self._models.clear()
            self._pipeline = None
            self.models_loaded = False
            
            logger.info("Model cleanup completed")
            
        except Exception as e:
            logger.error("Failed to cleanup models", error=str(e), exc_info=True)


# Global model service instance
_model_service = None


@lru_cache(maxsize=1)
def get_model_service() -> ModelService:
    """Get the global model service instance."""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service


async def initialize_model_service():
    """Initialize the global model service."""
    service = get_model_service()
    await service.initialize()
    return service


async def cleanup_model_service():
    """Clean up the global model service."""
    global _model_service
    if _model_service is not None:
        await _model_service.cleanup()
        _model_service = None
