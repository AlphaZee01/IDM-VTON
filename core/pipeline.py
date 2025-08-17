"""
Core pipeline for IDM-VTON virtual try-on.
Unified pipeline that works with both Gradio and FastAPI.
"""

import time
import torch
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from PIL import Image
import structlog
from functools import lru_cache

from config import settings, get_model_paths
from torchvision import transforms
from torchvision.transforms.functional import to_pil_image

logger = structlog.get_logger()


class TryOnPipeline:
    """Main try-on pipeline class with configurable parameters."""
    
    def __init__(self):
        self.device = settings.device
        self.model_paths = get_model_paths()
        self.base_path = settings.hf_model_name
        
        # Image transformations
        self.tensor_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5]),
        ])
        
        # Model components (loaded on-demand)
        self._models = {}
        self._pipeline = None
        self._parsing_model = None
        self._openpose_model = None
        
    async def initialize(self):
        """Initialize the pipeline and load models."""
        try:
            logger.info("Initializing TryOn pipeline")
            
            # Load models asynchronously
            await self._load_models()
            
            logger.info("TryOn pipeline initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize TryOn pipeline", error=str(e), exc_info=True)
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
        from preprocess.humanparsing.run_parsing import Parsing
        from preprocess.openpose.run_openpose import OpenPose
        
        logger.info("Loading TryOn models")
        
        # Load main model components
        self._models['unet'] = UNet2DConditionModel.from_pretrained(
            self.base_path,
            subfolder="unet",
            torch_dtype=torch.float16,
        )
        
        self._models['unet_encoder'] = UNet2DConditionModel_ref.from_pretrained(
            self.base_path,
            subfolder="unet_encoder",
            torch_dtype=torch.float16,
        )
        
        # Load tokenizers
        self._models['tokenizer_one'] = AutoTokenizer.from_pretrained(
            self.base_path,
            subfolder="tokenizer",
            revision=None,
            use_fast=False,
        )
        
        self._models['tokenizer_two'] = AutoTokenizer.from_pretrained(
            self.base_path,
            subfolder="tokenizer_2",
            revision=None,
            use_fast=False,
        )
        
        # Load text encoders
        self._models['text_encoder_one'] = CLIPTextModel.from_pretrained(
            self.base_path,
            subfolder="text_encoder",
            torch_dtype=torch.float16,
        )
        
        self._models['text_encoder_two'] = CLIPTextModelWithProjection.from_pretrained(
            self.base_path,
            subfolder="text_encoder_2",
            torch_dtype=torch.float16,
        )
        
        # Load image encoder
        self._models['image_encoder'] = CLIPVisionModelWithProjection.from_pretrained(
            self.base_path,
            subfolder="image_encoder",
            torch_dtype=torch.float16,
        )
        
        # Load VAE and scheduler
        self._models['vae'] = AutoencoderKL.from_pretrained(
            self.base_path,
            subfolder="vae",
            torch_dtype=torch.float16,
        )
        
        self._models['scheduler'] = DDPMScheduler.from_pretrained(
            self.base_path, 
            subfolder="scheduler"
        )
        
        # Move models to device and disable gradients
        for name, model in self._models.items():
            if hasattr(model, 'to'):
                model.to(self.device)
                model.requires_grad_(False)
        
        # Create pipeline
        self._pipeline = TryonPipeline.from_pretrained(
            self.base_path,
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
        
        # Load preprocessing models
        self._parsing_model = Parsing(0)
        self._openpose_model = OpenPose(0)
        
        logger.info("All TryOn models loaded successfully")
    
    def pil_to_binary_mask(self, pil_image: Image.Image, threshold: int = 0) -> Image.Image:
        """Convert PIL image to binary mask."""
        np_image = np.array(pil_image)
        grayscale_image = Image.fromarray(np_image).convert("L")
        binary_mask = np.array(grayscale_image) > threshold
        mask = np.zeros(binary_mask.shape, dtype=np.uint8)
        for i in range(binary_mask.shape[0]):
            for j in range(binary_mask.shape[1]):
                if binary_mask[i, j] == True:
                    mask[i, j] = 1
        mask = (mask * 255).astype(np.uint8)
        output_mask = Image.fromarray(mask)
        return output_mask
    
    async def process_tryon(
        self,
        human_image: Image.Image,
        garment_image: Image.Image,
        garment_description: str,
        mask_image: Optional[Image.Image] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[Image.Image, Image.Image]:
        """Process virtual try-on with the given inputs."""
        try:
            start_time = time.time()
            
            # Set default parameters
            if parameters is None:
                parameters = {}
            
            auto_mask = parameters.get('auto_mask', True)
            auto_crop = parameters.get('auto_crop', False)
            num_inference_steps = parameters.get('num_inference_steps', settings.num_inference_steps)
            seed = parameters.get('seed', None)
            
            # Ensure models are loaded
            if self._pipeline is None:
                await self.initialize()
            
            # Resize images to target dimensions
            garment_resized = garment_image.convert("RGB").resize((settings.image_width, settings.image_height))
            human_orig = human_image.convert("RGB")
            
            # Apply auto-cropping if requested
            crop_info = None
            if auto_crop:
                human_orig, crop_info = self._auto_crop_image(human_orig)
            
            human_resized = human_orig.resize((settings.image_width, settings.image_height))
            
            # Generate or use provided mask
            if auto_mask and mask_image is None:
                mask_image = await self._generate_mask(human_resized)
            elif mask_image is None:
                # Create default mask (full image)
                mask_image = Image.new('L', (settings.image_width, settings.image_height), 255)
            else:
                # Resize provided mask
                mask_image = mask_image.resize((settings.image_width, settings.image_height))
            
            # Generate pose estimation
            pose_image = await self._generate_pose(human_resized)
            
            # Process mask
            mask_gray = (1 - self.tensor_transform(mask_image)) * self.tensor_transform(human_resized)
            mask_gray = to_pil_image((mask_gray + 1.0) / 2.0)
            
            # Run inference
            result_image = await self._run_inference(
                human_resized=human_resized,
                garment_resized=garment_resized,
                mask_image=mask_image,
                pose_image=pose_image,
                garment_description=garment_description,
                num_inference_steps=num_inference_steps,
                seed=seed
            )
            
            # Apply cropping if needed
            if auto_crop and crop_info:
                result_image = self._apply_crop_result(result_image, crop_info, human_image)
            
            duration = time.time() - start_time
            logger.info(
                "Try-on processing completed",
                duration=duration,
                auto_mask=auto_mask,
                auto_crop=auto_crop,
                steps=num_inference_steps
            )
            
            return result_image, mask_gray
            
        except Exception as e:
            logger.error("Try-on processing failed", error=str(e), exc_info=True)
            raise
    
    def _auto_crop_image(self, image: Image.Image) -> Tuple[Image.Image, Dict[str, Any]]:
        """Automatically crop image to focus on the person."""
        width, height = image.size
        target_width = int(min(width, height * (3 / 4)))
        target_height = int(min(height, width * (4 / 3)))
        
        left = (width - target_width) / 2
        top = (height - target_height) / 2
        right = (width + target_width) / 2
        bottom = (height + target_height) / 2
        
        cropped_img = image.crop((left, top, right, bottom))
        crop_info = {
            'left': left, 'top': top, 'right': right, 'bottom': bottom,
            'crop_size': cropped_img.size
        }
        
        return cropped_img, crop_info
    
    async def _generate_mask(self, human_image: Image.Image) -> Image.Image:
        """Generate mask using parsing and pose estimation."""
        try:
            if self._parsing_model is None or self._openpose_model is None:
                logger.warning("Parsing or OpenPose model not available, using default mask")
                return Image.new('L', (settings.image_width, settings.image_height), 255)
            
            # Resize for processing
            human_small = human_image.resize((384, 512))
            
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
    
    async def _run_inference(
        self,
        human_resized: Image.Image,
        garment_resized: Image.Image,
        mask_image: Image.Image,
        pose_image: Image.Image,
        garment_description: str,
        num_inference_steps: int = 30,
        seed: Optional[int] = None
    ) -> Image.Image:
        """Run the actual inference."""
        try:
            with torch.no_grad():
                with torch.cuda.amp.autocast():
                    # Generate prompts
                    prompt = "model is wearing " + garment_description
                    negative_prompt = "monochrome, lowres, bad anatomy, worst quality, low quality"
                    
                    # Encode prompts
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
                    
                    # Encode garment prompt
                    cloth_prompt = "a photo of " + garment_description
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
                    
                    # Prepare tensors
                    pose_tensor = self.tensor_transform(pose_image).unsqueeze(0).to(self.device, torch.float16)
                    garment_tensor = self.tensor_transform(garment_resized).unsqueeze(0).to(self.device, torch.float16)
                    
                    # Set generator for reproducibility
                    generator = torch.Generator(self.device).manual_seed(seed) if seed is not None else None
                    
                    # Run inference
                    images = self._pipeline(
                        prompt_embeds=prompt_embeds.to(self.device, torch.float16),
                        negative_prompt_embeds=negative_prompt_embeds.to(self.device, torch.float16),
                        pooled_prompt_embeds=pooled_prompt_embeds.to(self.device, torch.float16),
                        negative_pooled_prompt_embeds=negative_pooled_prompt_embeds.to(self.device, torch.float16),
                        num_inference_steps=num_inference_steps,
                        generator=generator,
                        strength=1.0,
                        pose_img=pose_tensor,
                        text_embeds_cloth=prompt_embeds_c.to(self.device, torch.float16),
                        cloth=garment_tensor,
                        mask_image=mask_image,
                        image=human_resized,
                        height=settings.image_height,
                        width=settings.image_width,
                        ip_adapter_image=garment_resized,
                        guidance_scale=settings.guidance_scale,
                    )[0]
                    
                    return images[0]
                    
        except Exception as e:
            logger.error("Inference failed", error=str(e), exc_info=True)
            raise
    
    def _apply_crop_result(self, result_image: Image.Image, crop_info: Dict[str, Any], original_image: Image.Image) -> Image.Image:
        """Apply cropping result back to original image."""
        try:
            out_img = result_image.resize(crop_info['crop_size'])
            original_image.paste(out_img, (int(crop_info['left']), int(crop_info['top'])))
            return original_image
        except Exception as e:
            logger.warning("Failed to apply crop result", error=str(e))
            return result_image
    
    async def cleanup(self):
        """Clean up pipeline resources."""
        try:
            logger.info("Cleaning up TryOn pipeline")
            
            # Clear models
            self._models.clear()
            self._pipeline = None
            self._parsing_model = None
            self._openpose_model = None
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("TryOn pipeline cleanup completed")
            
        except Exception as e:
            logger.error("Failed to cleanup TryOn pipeline", error=str(e), exc_info=True)


# Global pipeline instance
_tryon_pipeline = None


@lru_cache(maxsize=1)
def get_tryon_pipeline() -> TryOnPipeline:
    """Get the global TryOn pipeline instance."""
    global _tryon_pipeline
    if _tryon_pipeline is None:
        _tryon_pipeline = TryOnPipeline()
    return _tryon_pipeline


async def initialize_tryon_pipeline():
    """Initialize the global TryOn pipeline."""
    pipeline = get_tryon_pipeline()
    await pipeline.initialize()
    return pipeline


async def cleanup_tryon_pipeline():
    """Clean up the global TryOn pipeline."""
    global _tryon_pipeline
    if _tryon_pipeline is not None:
        await _tryon_pipeline.cleanup()
        _tryon_pipeline = None
