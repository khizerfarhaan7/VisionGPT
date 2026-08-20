import gc
import logging
import threading
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Centralized, thread-safe AI Model Manager for VisionGPT.
    Enforces singleton instance per model, lazy loading on demand,
    and explicit memory release/garbage collection for 4 GB RAM safety.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._models: Dict[str, Any] = {}
        logger.info(
            f"ModelManager initialized in LAZY mode (no models loaded on startup). "
            f"Active Profile: '{getattr(settings, 'VISIONGPT_PROFILE', 'local').upper()}'. "
            f"Configured models -> Embedding: '{getattr(settings, 'EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')}', "
            f"Whisper: '{getattr(settings, 'WHISPER_MODEL', 'small')}' ({getattr(settings, 'WHISPER_DEVICE', 'cpu')}/{getattr(settings, 'WHISPER_COMPUTE_TYPE', 'int8')}), "
            f"Florence-2: '{getattr(settings, 'FLORENCE_MODEL_ID', 'microsoft/Florence-2-base')}', "
            f"Ollama: '{getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:3b')}'."
        )

    def is_loaded(self, model_name: str) -> bool:
        """
        Check if a specific model is currently cached in memory.
        """
        with self._lock:
            return model_name in self._models and self._models[model_name] is not None

    def get_embedding_model(self, model_name: Optional[str] = None) -> Any:
        """
        Lazy-loads or returns cached SentenceTransformer embedding model.
        """
        model_key = "embedding"
        target_model = model_name or getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

        with self._lock:
            if model_key in self._models and self._models[model_key] is not None:
                logger.info(f"ModelManager: Model '{model_key}' reused from cache.")
                return self._models[model_key]

            logger.info(f"ModelManager: Model '{model_key}' requested. Loading '{target_model}'...")
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(target_model)
                self._models[model_key] = model
                logger.info(f"ModelManager: Model '{model_key}' ({target_model}) loaded successfully.")
                return model
            except Exception as e:
                logger.error(f"ModelManager: Failed to load embedding model '{target_model}': {e}", exc_info=True)
                raise RuntimeError(f"Embedding model loading failed: {str(e)}") from e

    def get_whisper_model(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None
    ) -> Any:
        """
        Lazy-loads or returns the single managed Faster-Whisper model instance.
        """
        model_key = "whisper"
        target_size = model_size or getattr(settings, "WHISPER_MODEL", "small")
        target_device = device or getattr(settings, "WHISPER_DEVICE", "cpu")
        target_compute = compute_type or getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")

        # CUDA availability check & fallback
        import torch
        if target_device == "cuda" and not torch.cuda.is_available():
            logger.warning(
                f"ModelManager: WHISPER_DEVICE='cuda' was requested, but CUDA is not available on host. "
                "Falling back to device='cpu' with compute_type='int8'."
            )
            target_device = "cpu"
            target_compute = "int8"

        with self._lock:
            if model_key in self._models and self._models[model_key] is not None:
                logger.info(f"ModelManager: Model '{model_key}' reused from cache.")
                return self._models[model_key]

            logger.info(
                f"ModelManager: Model '{model_key}' requested. "
                f"Initializing faster-whisper ('{target_size}', device='{target_device}', compute='{target_compute}')..."
            )
            try:
                import faster_whisper
                try:
                    model = faster_whisper.WhisperModel(
                        target_size,
                        device=target_device,
                        compute_type=target_compute
                    )
                    logger.info(f"ModelManager: Model '{model_key}' loaded successfully on device '{target_device}'.")
                except Exception as primary_err:
                    if target_device != "cpu":
                        logger.warning(
                            f"ModelManager: Primary device '{target_device}' failed for Whisper ({primary_err}). "
                            "Attempting CPU fallback with int8 quantization..."
                        )
                        model = faster_whisper.WhisperModel(
                            target_size,
                            device="cpu",
                            compute_type="int8"
                        )
                        logger.info(f"ModelManager: Model '{model_key}' loaded successfully on CPU (int8 fallback).")
                    else:
                        raise primary_err

                self._models[model_key] = model
                return model

            except Exception as e:
                logger.critical(f"ModelManager: Failed to initialize Whisper model '{model_key}': {e}", exc_info=True)
                raise RuntimeError(f"Speech recognition model loading failed: {str(e)}") from e

    def get_florence_model(
        self,
        model_id: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """
        Lazy-loads or returns cached Microsoft Florence-2 processor and model pair.
        """
        model_key = "florence"
        target_id = model_id or getattr(settings, "FLORENCE_MODEL_ID", "microsoft/Florence-2-base")

        with self._lock:
            if model_key in self._models and self._models[model_key] is not None:
                logger.info(f"ModelManager: Model '{model_key}' reused from cache.")
                return self._models[model_key]

            logger.info(f"ModelManager: Model '{model_key}' requested. Initializing '{target_id}'...")
            try:
                import torch
                import transformers.dynamic_module_utils

                # Override check_imports to bypass flash_attn check on Windows/CPU environments
                orig_check_imports = transformers.dynamic_module_utils.check_imports

                def patched_check_imports(filename, *args, **kwargs):
                    try:
                        return orig_check_imports(filename, *args, **kwargs)
                    except ImportError as e:
                        if "flash_attn" in str(e):
                            return transformers.dynamic_module_utils.get_relative_imports(filename)
                        raise e

                transformers.dynamic_module_utils.check_imports = patched_check_imports

                from transformers import AutoProcessor, AutoModelForCausalLM

                requested_device = getattr(settings, "FLORENCE_DEVICE", "cpu")
                if requested_device == "cuda" and not torch.cuda.is_available():
                    logger.warning(
                        "ModelManager: FLORENCE_DEVICE='cuda' requested, but PyTorch CUDA is unavailable. "
                        "Falling back to device='cpu'."
                    )
                    requested_device = "cpu"

                device = requested_device if (requested_device == "cuda" and torch.cuda.is_available()) else "cpu"
                torch_dtype = torch.float16 if device == "cuda" else torch.float32

                processor = AutoProcessor.from_pretrained(target_id, trust_remote_code=True)
                model = AutoModelForCausalLM.from_pretrained(
                    target_id,
                    torch_dtype=torch_dtype,
                    trust_remote_code=True
                ).to(device)

                pair = (processor, model)
                self._models[model_key] = pair
                logger.info(f"ModelManager: Model '{model_key}' loaded successfully on device '{device}'.")
                return pair

            except Exception as e:
                logger.error(f"ModelManager: Failed to load Florence-2 vision model '{model_key}': {e}", exc_info=True)
                raise RuntimeError(f"Florence-2 loading failed: {str(e)}") from e

    def release_model(self, model_name: str) -> bool:
        """
        Explicitly unloads a model from memory and triggers garbage collection.
        Crucial for heavy models like Florence-2 on 4 GB RAM systems.
        """
        with self._lock:
            if model_name not in self._models or self._models[model_name] is None:
                logger.info(f"ModelManager: Release requested for '{model_name}', but it was not loaded.")
                return False

            logger.info(f"ModelManager: Unloading model '{model_name}' and releasing memory resources...")
            del self._models[model_name]
            self._models[model_name] = None
            del self._models[model_name]

            # Perform immediate garbage collection
            gc.collect()

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            logger.info(f"ModelManager: Model '{model_name}' successfully unloaded. RAM/VRAM garbage collected.")
            return True

    def unload_all() -> None:
        """
        Unload all cached models and clean up system memory.
        """
        with self._lock:
            keys = list(self._models.keys())
            for key in keys:
                if self._models.get(key) is not None:
                    logger.info(f"ModelManager: Unloading '{key}' during bulk cleanup...")
                    del self._models[key]

            self._models.clear()
            gc.collect()

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            logger.info("ModelManager: All models cleared from memory.")


# Singleton container instance
model_manager = ModelManager()
