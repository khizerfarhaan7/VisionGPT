import logging
import io
from abc import ABC, abstractmethod
from typing import Union, BinaryIO, Optional
from pathlib import Path
from PIL import Image
import torch

from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseVisionModel(ABC):
    """
    Abstract Base Class representing a Vision Model implementation backend.
    Enables swapping underlying vision models (e.g., Florence-2, BLIP, LLaVA)
    without affecting downstream modules.
    """
    @abstractmethod
    def load_model(self) -> None:
        """Loads and initializes the model weights and processors into memory."""
        pass

    @abstractmethod
    def describe_image(self, image: Image.Image) -> str:
        """
        Generates a natural language description/caption for a PIL Image.
        """
        pass


from app.core.model_manager import model_manager

class Florence2Model(BaseVisionModel):
    """
    Microsoft Florence-2-base vision model backend implementation.
    Integrates with ModelManager for lazy loading and 4 GB RAM auto-release.
    """
    def __init__(self, model_id: str = "microsoft/Florence-2-base", auto_release: bool = True):
        self.model_id = model_id
        self.auto_release = auto_release
        self.model = None
        self.processor = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    def load_model(self) -> None:
        """
        Lazy loads Florence-2 processor and model pair via ModelManager.
        """
        self.processor, self.model = model_manager.get_florence_model(self.model_id)
        if hasattr(self.model, "device"):
            self.device = str(self.model.device)

    def describe_image(self, image: Image.Image) -> str:
        """
        Executes image caption generation and auto-releases model memory if configured.
        """
        self.load_model()
        
        try:
            prompt = "<MORE_DETAILED_CAPTION>"
            
            # Preprocess image
            inputs = self.processor(text=prompt, images=image, return_tensors="pt")
            
            # Send to correct device and type cast values
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            if self.torch_dtype == torch.float16 and "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)
                
            # Run causal generation
            with torch.no_grad():
                generated_ids = self.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    num_beams=3
                )
                
            # Decode output
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            description = generated_text.strip()
            
            # Clean up Florence-2 return prefixes
            if description.startswith(prompt):
                description = description[len(prompt):].strip()
                
            return description
        except Exception as e:
            logger.exception("Inference error during Florence-2 image description execution")
            raise RuntimeError(f"Florence-2 captioning failed: {str(e)}") from e
        finally:
            if self.auto_release:
                model_manager.release_model("florence")


class VisionService:
    """
    High-level Vision Service offering a consistent, model-agnostic entrance point
    for image and frame analyses.
    """
    def __init__(self, backend_model: Optional[BaseVisionModel] = None):
        self._backend = backend_model or Florence2Model()

    def describe_image(self, image: Union[Image.Image, str, Path, bytes, BinaryIO]) -> str:
        """
        Unified service method to generate a textual description of an image input.
        Accepts PIL Images, local file paths, raw bytes or streams.
        """
        pil_image = self._convert_to_pil(image)
        try:
            return self._backend.describe_image(pil_image)
        except Exception as e:
            logger.error(f"VisionService description generation failed: {str(e)}")
            raise e

    def _convert_to_pil(self, image: Union[Image.Image, str, Path, bytes, BinaryIO]) -> Image.Image:
        """
        Utility method to ensure any incoming format maps cleanly to an RGB PIL Image.
        """
        if isinstance(image, Image.Image):
            return image
            
        try:
            if isinstance(image, (str, Path)):
                return Image.open(str(image)).convert("RGB")
            if isinstance(image, bytes):
                return Image.open(io.BytesIO(image)).convert("RGB")
            # Try reading as a stream/file-like object
            return Image.open(image).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to decode image input to PIL Image: {str(e)}")
            raise ValueError(f"Unsupported or corrupt image source format: {str(e)}") from e


# Singleton container
_vision_service_instance = None

def get_vision_service() -> VisionService:
    """
    Retrieves the singleton VisionService instance.
    """
    global _vision_service_instance
    if _vision_service_instance is None:
        _vision_service_instance = VisionService()
    return _vision_service_instance

def describe_image(image: Union[Image.Image, str, Path, bytes, BinaryIO]) -> str:
    """
    Helper wrapper pointing to the shared VisionService singleton.
    """
    return get_vision_service().describe_image(image)
