"""
Refactored Gradio demo for IDM-VTON.
Uses the new core pipeline and proper error handling.
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

import gradio as gr
from PIL import Image
import structlog

from config import settings
from core.pipeline import get_tryon_pipeline, initialize_tryon_pipeline
from core.exceptions import (
    IDMVTONError, ValidationError, ImageValidationError, 
    create_user_friendly_error, get_error_response
)

logger = structlog.get_logger()

# Global pipeline instance
_pipeline = None


async def initialize_pipeline():
    """Initialize the try-on pipeline."""
    global _pipeline
    try:
        _pipeline = await initialize_tryon_pipeline()
        logger.info("Pipeline initialized for Gradio demo")
    except Exception as e:
        logger.error("Failed to initialize pipeline", error=str(e), exc_info=True)
        raise


def validate_image(image: Image.Image, field_name: str) -> None:
    """Validate image for processing."""
    if image is None:
        raise ImageValidationError(field_name, "Image is required")
    
    width, height = image.size
    
    # Check image dimensions
    if width < 256 or height < 256:
        raise ImageValidationError(
            field_name, 
            f"Image too small. Minimum size: 256x256 pixels, got: {width}x{height}"
        )
    
    if width > 2048 or height > 2048:
        raise ImageValidationError(
            field_name, 
            f"Image too large. Maximum size: 2048x2048 pixels, got: {width}x{height}"
        )
    
    # Check aspect ratio
    aspect_ratio = width / height
    if aspect_ratio < 0.5 or aspect_ratio > 2.0:
        raise ImageValidationError(
            field_name, 
            f"Image aspect ratio too extreme. Should be between 0.5 and 2.0, got: {aspect_ratio:.2f}"
        )


def validate_parameters(parameters: Dict[str, Any]) -> None:
    """Validate processing parameters."""
    num_inference_steps = parameters.get('num_inference_steps', 30)
    if not isinstance(num_inference_steps, int) or num_inference_steps < 20 or num_inference_steps > 40:
        raise ValidationError(
            "num_inference_steps", 
            num_inference_steps, 
            "Must be an integer between 20 and 40"
        )
    
    seed = parameters.get('seed')
    if seed is not None:
        if not isinstance(seed, int) or seed < -1 or seed > 2147483647:
            raise ValidationError(
                "seed", 
                seed, 
                "Must be an integer between -1 and 2147483647"
            )


async def process_tryon_async(
    human_image: Image.Image,
    garment_image: Image.Image,
    garment_description: str,
    auto_mask: bool = True,
    auto_crop: bool = False,
    num_inference_steps: int = 30,
    seed: Optional[int] = None
) -> tuple[Image.Image, Image.Image]:
    """Process virtual try-on asynchronously."""
    try:
        # Validate inputs
        validate_image(human_image, "human_image")
        validate_image(garment_image, "garment_image")
        
        if not garment_description or not garment_description.strip():
            raise ValidationError("garment_description", garment_description, "Description is required")
        
        parameters = {
            'auto_mask': auto_mask,
            'auto_crop': auto_crop,
            'num_inference_steps': num_inference_steps,
            'seed': seed
        }
        validate_parameters(parameters)
        
        # Ensure pipeline is initialized
        global _pipeline
        if _pipeline is None:
            await initialize_pipeline()
        
        # Process try-on
        result_image, mask_image = await _pipeline.process_tryon(
            human_image=human_image,
            garment_image=garment_image,
            garment_description=garment_description.strip(),
            parameters=parameters
        )
        
        return result_image, mask_image
        
    except IDMVTONError as e:
        logger.error("Try-on processing failed", error=str(e), exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error during try-on processing", error=str(e), exc_info=True)
        raise IDMVTONError(f"Unexpected error: {str(e)}")


def process_tryon_sync(*args):
    """Synchronous wrapper for async try-on processing."""
    try:
        # Extract arguments
        human_dict, garment_image, garment_description, auto_mask, auto_crop, num_inference_steps, seed = args
        
        # Extract human image from dict
        if isinstance(human_dict, dict) and 'background' in human_dict:
            human_image = human_dict['background']
        else:
            human_image = human_dict
        
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                process_tryon_async(
                    human_image=human_image,
                    garment_image=garment_image,
                    garment_description=garment_description,
                    auto_mask=auto_mask,
                    auto_crop=auto_crop,
                    num_inference_steps=num_inference_steps,
                    seed=seed
                )
            )
            return result
        finally:
            loop.close()
            
    except IDMVTONError as e:
        # Return error images with error message
        error_msg = create_user_friendly_error(e)
        logger.error("Try-on failed", error=error_msg)
        
        # Create error image
        error_image = Image.new('RGB', (768, 1024), (255, 200, 200))
        # You could add text to the error image here if needed
        
        return error_image, error_image


def create_demo():
    """Create the Gradio demo interface."""
    # Load example images
    example_path = Path(__file__).parent / "example"
    
    garment_list = list((example_path / "cloth").glob("*.jpg"))
    garment_list_path = [str(path) for path in garment_list]
    
    human_list = list((example_path / "human").glob("*.jpg"))
    human_ex_list = []
    for human_path in human_list:
        ex_dict = {
            'background': str(human_path),
            'layers': None,
            'composite': None
        }
        human_ex_list.append(ex_dict)
    
    # Create Gradio interface
    with gr.Blocks(title="IDM-VTON Refactored", theme=gr.themes.Soft()) as demo:
        gr.Markdown("## IDM-VTON 👕👔👚 (Refactored)")
        gr.Markdown(
            "Virtual Try-on with your image and garment image. "
            "Check out the [source codes](https://github.com/yisol/IDM-VTON) "
            "and the [model](https://huggingface.co/yisol/IDM-VTON)"
        )
        
        with gr.Row():
            with gr.Column():
                imgs = gr.ImageEditor(
                    sources='upload', 
                    type="pil", 
                    label='Human. Mask with pen or use auto-masking', 
                    interactive=True
                )
                with gr.Row():
                    is_checked = gr.Checkbox(
                        label="Yes", 
                        info="Use auto-generated mask (Takes 5 seconds)",
                        value=True
                    )
                with gr.Row():
                    is_checked_crop = gr.Checkbox(
                        label="Yes", 
                        info="Use auto-crop & resizing",
                        value=False
                    )
                
                example = gr.Examples(
                    inputs=imgs,
                    examples_per_page=10,
                    examples=human_ex_list
                )
            
            with gr.Column():
                garm_img = gr.Image(
                    label="Garment", 
                    sources='upload', 
                    type="pil"
                )
                with gr.Row(elem_id="prompt-container"):
                    with gr.Row():
                        prompt = gr.Textbox(
                            placeholder="Description of garment ex) Short Sleeve Round Neck T-shirts", 
                            show_label=False, 
                            elem_id="prompt"
                        )
                example = gr.Examples(
                    inputs=garm_img,
                    examples_per_page=8,
                    examples=garment_list_path
                )
            
            with gr.Column():
                masked_img = gr.Image(
                    label="Masked image output", 
                    elem_id="masked-img",
                    show_share_button=False
                )
            
            with gr.Column():
                image_out = gr.Image(
                    label="Output", 
                    elem_id="output-img",
                    show_share_button=False
                )
        
        with gr.Column():
            try_button = gr.Button(value="Try-on", variant="primary")
            
            with gr.Accordion(label="Advanced Settings", open=False):
                with gr.Row():
                    denoise_steps = gr.Number(
                        label="Denoising Steps", 
                        minimum=20, 
                        maximum=40, 
                        value=30, 
                        step=1
                    )
                    seed = gr.Number(
                        label="Seed", 
                        minimum=-1, 
                        maximum=2147483647, 
                        step=1, 
                        value=42
                    )
        
        # Connect the button
        try_button.click(
            fn=process_tryon_sync, 
            inputs=[imgs, garm_img, prompt, is_checked, is_checked_crop, denoise_steps, seed], 
            outputs=[image_out, masked_img], 
            api_name='tryon'
        )
        
        # Add error handling
        demo.load(initialize_pipeline)
    
    return demo


if __name__ == "__main__":
    # Initialize logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create and launch demo
    demo = create_demo()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=settings.debug
    )
