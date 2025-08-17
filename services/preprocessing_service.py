"""
Preprocessing service for IDM-VTON.
Handles image preprocessing, mask generation, and pose estimation.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import torch
import numpy as np
from PIL import Image
import structlog
from functools import lru_cache

from config import settings, get_model_paths
from torchvision import transforms

logger = structlog.get_logger()


class PreprocessingService:
    """Service for preprocessing images for virtual try-on."""
    
    def __init__(self):
        self.model_paths = get_model_paths()
        self.device = settings.device
        self._parsing_model = None
        self._openpose_model = None
        self._densepose_model = None
        
        # Image transformations
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5]),
        ])
        
    async def initialize(self):
        """Initialize preprocessing models."""
        try:
            logger.info("Initializing preprocessing service")
            
            # Initialize models asynchronously
            await asyncio.gather(
                self._load_parsing_model(),
                self._load_openpose_model(),
                self._load_densepose_model()
            )
            
            logger.info("Preprocessing service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize preprocessing service", error=str(e), exc_info=True)
            raise
    
    async def _load_parsing_model(self):
        """Load human parsing model."""
        try:
            from preprocess.humanparsing.run_parsing import Parsing
            self._parsing_model = Parsing(0)  # Use GPU 0
            logger.info("Human parsing model loaded")
        except Exception as e:
            logger.warning("Failed to load human parsing model", error=str(e))
            self._parsing_model = None
    
    async def _load_openpose_model(self):
        """Load OpenPose model."""
        try:
            from preprocess.openpose.run_openpose import OpenPose
            self._openpose_model = OpenPose(0)  # Use GPU 0
            logger.info("OpenPose model loaded")
        except Exception as e:
            logger.warning("Failed to load OpenPose model", error=str(e))
            self._openpose_model = None
    
    async def _load_densepose_model(self):
        """Load DensePose model."""
        try:
            # DensePose is loaded on-demand in apply_net
            logger.info("DensePose model will be loaded on-demand")
        except Exception as e:
            logger.warning("Failed to load DensePose model", error=str(e))
    
    async def preprocess_images(
        self,
        human_image: Image.Image,
        garment_image: Image.Image,
        auto_mask: bool = True,
        auto_crop: bool = False
    ) -> Dict[str, Any]:
        """Preprocess human and garment images for try-on."""
        try:
            start_time = time.time()
            
            # Resize images to target dimensions
            human_resized = human_image.convert("RGB").resize((settings.image_width, settings.image_height))
            garment_resized = garment_image.convert("RGB").resize((settings.image_width, settings.image_height))
            
            # Apply auto-cropping if requested
            if auto_crop:
                human_resized = await self._auto_crop_image(human_resized)
            
            # Generate mask if auto-mask is enabled
            mask_image = None
            if auto_mask:
                mask_image = await self._generate_mask(human_resized)
            else:
                # Create a default mask (full image)
                mask_image = Image.new('L', (settings.image_width, settings.image_height), 255)
            
            # Generate pose estimation
            pose_image = await self._generate_pose(human_resized)
            
            # Convert to tensors
            human_tensor = self.transform(human_resized).unsqueeze(0)
            garment_tensor = self.transform(garment_resized).unsqueeze(0)
            mask_tensor = transforms.ToTensor()(mask_image).unsqueeze(0)
            pose_tensor = self.transform(pose_image).unsqueeze(0)
            
            duration = time.time() - start_time
            logger.info(
                "Image preprocessing completed",
                duration=duration,
                auto_mask=auto_mask,
                auto_crop=auto_crop
            )
            
            return {
                "human_tensor": human_tensor,
                "garment_tensor": garment_tensor,
                "mask_tensor": mask_tensor,
                "pose_tensor": pose_tensor,
                "human_image": human_resized,
                "garment_image": garment_resized,
                "mask_image": mask_image,
                "pose_image": pose_image,
                "processing_time": duration
            }
            
        except Exception as e:
            logger.error("Failed to preprocess images", error=str(e), exc_info=True)
            raise
    
    async def _auto_crop_image(self, image: Image.Image) -> Image.Image:
        """Automatically crop and resize image to focus on the person."""
        try:
            # Simple center crop for now - can be enhanced with person detection
            width, height = image.size
            target_width = int(min(width, height * (3 / 4)))
            target_height = int(min(height, width * (4 / 3)))
            
            left = (width - target_width) // 2
            top = (height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            
            cropped = image.crop((left, top, right, bottom))
            return cropped.resize((settings.image_width, settings.image_height))
            
        except Exception as e:
            logger.warning("Auto-crop failed, using original image", error=str(e))
            return image.resize((settings.image_width, settings.image_height))
    
    async def _generate_mask(self, human_image: Image.Image) -> Image.Image:
        """Generate mask for the human image using parsing and pose estimation."""
        try:
            if self._parsing_model is None or self._openpose_model is None:
                logger.warning("Parsing or OpenPose model not available, using default mask")
                return Image.new('L', (settings.image_width, settings.image_height), 255)
            
            # Resize for processing
            process_size = (384, 512)
            human_small = human_image.resize(process_size)
            
            # Get pose keypoints
            keypoints = self._openpose_model(human_small)
            
            # Get parsing mask
            model_parse, _ = self._parsing_model(human_small)
            
            # Generate mask using existing utility
            from utils_mask import get_mask_location
            mask, _ = get_mask_location('hd', "upper_body", model_parse, keypoints)
            
            # Resize back to target size
            mask = mask.resize((settings.image_width, settings.image_height))
            
            return mask
            
        except Exception as e:
            logger.warning("Mask generation failed, using default mask", error=str(e))
            return Image.new('L', (settings.image_width, settings.image_height), 255)
    
    async def _generate_pose(self, human_image: Image.Image) -> Image.Image:
        """Generate pose estimation using DensePose."""
        try:
            # Import here to avoid circular imports
            import apply_net
            from detectron2.data.detection_utils import convert_PIL_to_numpy, _apply_exif_orientation
            
            # Prepare image for DensePose
            human_small = human_image.resize((384, 512))
            human_arg = _apply_exif_orientation(human_small)
            human_arg = convert_PIL_to_numpy(human_arg, format="BGR")
            
            # Run DensePose
            args = apply_net.create_argument_parser().parse_args((
                'show', 
                './configs/densepose_rcnn_R_50_FPN_s1x.yaml', 
                str(self.model_paths['densepose']), 
                'dp_segm', 
                '-v', 
                '--opts', 
                'MODEL.DEVICE', 
                'cuda' if torch.cuda.is_available() else 'cpu'
            ))
            
            pose_img = args.func(args, human_arg)
            pose_img = pose_img[:, :, ::-1]  # BGR to RGB
            pose_img = Image.fromarray(pose_img).resize((settings.image_width, settings.image_height))
            
            return pose_img
            
        except Exception as e:
            logger.warning("Pose generation failed, using human image as fallback", error=str(e))
            return human_image
    
    async def validate_image(self, image: Image.Image) -> Dict[str, Any]:
        """Validate image for processing."""
        try:
            width, height = image.size
            
            # Check image dimensions
            if width < 256 or height < 256:
                return {
                    "valid": False,
                    "error": "Image too small. Minimum size: 256x256 pixels"
                }
            
            if width > 2048 or height > 2048:
                return {
                    "valid": False,
                    "error": "Image too large. Maximum size: 2048x2048 pixels"
                }
            
            # Check aspect ratio
            aspect_ratio = width / height
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                return {
                    "valid": False,
                    "error": "Image aspect ratio too extreme. Should be between 0.5 and 2.0"
                }
            
            return {
                "valid": True,
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Image validation failed: {str(e)}"
            }
    
    async def enhance_image(self, image: Image.Image) -> Image.Image:
        """Apply basic image enhancement."""
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Basic enhancement - can be extended with more sophisticated methods
            from PIL import ImageEnhance
            
            # Slight contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.1)
            
            # Slight brightness adjustment
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.05)
            
            return image
            
        except Exception as e:
            logger.warning("Image enhancement failed", error=str(e))
            return image
    
    async def cleanup(self):
        """Clean up preprocessing resources."""
        try:
            logger.info("Cleaning up preprocessing service")
            
            # Clear models
            self._parsing_model = None
            self._openpose_model = None
            self._densepose_model = None
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Preprocessing service cleanup completed")
            
        except Exception as e:
            logger.error("Failed to cleanup preprocessing service", error=str(e), exc_info=True)


# Global preprocessing service instance
_preprocessing_service = None


@lru_cache(maxsize=1)
def get_preprocessing_service() -> PreprocessingService:
    """Get the global preprocessing service instance."""
    global _preprocessing_service
    if _preprocessing_service is None:
        _preprocessing_service = PreprocessingService()
    return _preprocessing_service


async def initialize_preprocessing_service():
    """Initialize the global preprocessing service."""
    service = get_preprocessing_service()
    await service.initialize()
    return service


async def cleanup_preprocessing_service():
    """Clean up the global preprocessing service."""
    global _preprocessing_service
    if _preprocessing_service is not None:
        await _preprocessing_service.cleanup()
        _preprocessing_service = None
