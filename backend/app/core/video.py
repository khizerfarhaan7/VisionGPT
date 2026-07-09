import os
import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, List, Dict, Any, Optional
from PIL import Image
import av

from app.core.config import settings

logger = logging.getLogger(__name__)

class FrameProcessor(ABC):
    """
    Interface for processors operating on individual extracted frames (e.g., OCR, Object Detection).
    """
    @abstractmethod
    def process_frame(self, frame_data: Dict[str, Any], image: Image.Image) -> Dict[str, Any]:
        """
        Processes a single frame and returns any extracted data/features.
        """
        pass


class VideoProcessor(ABC):
    """
    Interface for processors operating on the entire video (e.g., Audio Extraction, Scene Detection).
    """
    @abstractmethod
    def process_video(self, video_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the video file and returns any extracted features.
        """
        pass


class VideoService:
    """
    Video Service responsible for metadata reading, frame extraction,
    and managing post-processing hooks.
    """
    def __init__(self):
        self._frame_processors: List[FrameProcessor] = []
        self._video_processors: List[VideoProcessor] = []

    def register_frame_processor(self, processor: FrameProcessor) -> None:
        """Registers a processor to run on individual frames during/after extraction."""
        self._frame_processors.append(processor)
        logger.info(f"Registered frame processor: {processor.__class__.__name__}")

    def register_video_processor(self, processor: VideoProcessor) -> None:
        """Registers a processor to run on the entire video."""
        self._video_processors.append(processor)
        logger.info(f"Registered video processor: {processor.__class__.__name__}")

    def get_video_metadata(self, video_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Retrieves video metadata safely using PyAV.
        """
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        logger.info(f"Reading video metadata for: {video_file.name}")
        try:
            with av.open(str(video_file)) as container:
                video_streams = container.streams.video
                if not video_streams:
                    raise ValueError("No video stream found in container.")
                
                stream = video_streams[0]
                
                # Fetch duration
                duration = None
                if stream.duration and stream.time_base:
                    duration = float(stream.duration * stream.time_base)
                elif container.duration:
                    duration = float(container.duration / av.time_base)
                
                # Fetch FPS
                fps = None
                if stream.average_rate:
                    fps = float(stream.average_rate)
                elif stream.base_rate:
                    fps = float(stream.base_rate)
                
                # Fetch Codec
                codec = getattr(stream.codec_context, "name", None)
                
                # Build metadata dictionary
                metadata = {
                    "filename": video_file.name,
                    "duration": duration,
                    "fps": fps,
                    "width": stream.width,
                    "height": stream.height,
                    "total_frames": stream.frames,
                    "codec": codec,
                }
                
                logger.info(f"Successfully parsed video metadata: {metadata}")
                return metadata
        except Exception as e:
            logger.error(f"Error reading video metadata: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to read video metadata: {str(e)}") from e

    def extract_frames(
        self,
        video_path: Union[str, Path],
        interval_seconds: float = 3.0,
        output_dir: Optional[Union[str, Path]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts frames at a given interval, saving them in a temporary folder.
        Optionally runs registered frame processors on each extracted frame.
        """
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        # Set up a temporary directory if not provided
        if output_dir is None:
            video_id = video_file.stem
            output_path = Path(settings.UPLOAD_DIR) / "temp" / "video_processing" / video_id
        else:
            output_path = Path(output_dir)

        output_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Extracting frames for {video_file.name} to {output_path} (every {interval_seconds}s)")

        extracted_frames = []

        try:
            with av.open(str(video_file)) as container:
                video_streams = container.streams.video
                if not video_streams:
                    raise ValueError("No video stream found.")
                
                stream = video_streams[0]
                
                next_target_time = 0.0
                frame_count = 0
                extracted_count = 0
                
                for frame in container.decode(video=0):
                    # Calculate frame timestamp in seconds
                    pts_seconds = (
                        float(frame.pts * stream.time_base)
                        if frame.pts is not None and stream.time_base is not None
                        else (frame_count / float(stream.average_rate or 30.0))
                    )
                    
                    if pts_seconds >= next_target_time:
                        # Extract PIL image from PyAV VideoFrame
                        pil_img = frame.to_image()
                        
                        frame_filename = f"frame_{extracted_count:05d}_ts_{pts_seconds:.3f}.jpg"
                        frame_filepath = output_path / frame_filename
                        
                        # Save frame image
                        pil_img.save(frame_filepath, format="JPEG", quality=90)
                        
                        frame_data = {
                            "filename": frame_filename,
                            "timestamp": pts_seconds,
                            "frame_number": frame_count,
                            "file_path": str(frame_filepath)
                        }
                        
                        # Process frame using registered processors (e.g. OCR, detection)
                        for processor in self._frame_processors:
                            try:
                                processor_data = processor.process_frame(frame_data, pil_img)
                                if processor_data:
                                    frame_data.update(processor_data)
                            except Exception as pe:
                                logger.error(f"Error in frame processor {processor.__class__.__name__}: {str(pe)}")
                        
                        extracted_frames.append(frame_data)
                        extracted_count += 1
                        
                        # Set next target extraction timestamp
                        next_target_time = pts_seconds + interval_seconds
                        
                    frame_count += 1
                    
            logger.info(f"Extracted {len(extracted_frames)} frames successfully.")
            return extracted_frames
            
        except Exception as e:
            logger.error(f"Error during frame extraction: {str(e)}", exc_info=True)
            # Clean up the output directory if we had a failure
            self.cleanup_directory(output_path)
            raise ValueError(f"Failed to extract frames: {str(e)}") from e

    def process_video_features(self, video_path: Union[str, Path], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes any registered video-level processors (e.g., audio extraction, scene detection).
        """
        video_file = Path(video_path)
        logger.info(f"Running video-level processors for {video_file.name}")
        results = {}
        
        for processor in self._video_processors:
            try:
                processor_results = processor.process_video(video_file, metadata)
                if processor_results:
                    results[processor.__class__.__name__] = processor_results
            except Exception as e:
                logger.error(f"Error in video processor {processor.__class__.__name__}: {str(e)}")
                
        return results

    def cleanup_extracted_frames(self, frames: List[Dict[str, Any]]) -> None:
        """
        Utility method to clean up specific saved frame files.
        """
        logger.info("Cleaning up individual frame files...")
        for frame in frames:
            file_path = frame.get("file_path")
            if file_path:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete frame file {file_path}: {str(e)}")

    def cleanup_directory(self, dir_path: Union[str, Path]) -> None:
        """
        Utility method to clean up an entire temporary output directory.
        """
        p = Path(dir_path)
        if p.exists() and p.is_dir():
            logger.info(f"Cleaning up temporary directory: {p}")
            try:
                shutil.rmtree(p)
            except Exception as e:
                logger.error(f"Failed to delete directory {p}: {str(e)}")


# Singleton instance
_video_service_instance = None

def get_video_service() -> VideoService:
    """Gets the global singleton instance of VideoService."""
    global _video_service_instance
    if _video_service_instance is None:
        _video_service_instance = VideoService()
    return _video_service_instance

def get_video_metadata(video_path: Union[str, Path]) -> Dict[str, Any]:
    """Helper wrapper function to fetch video metadata."""
    return get_video_service().get_video_metadata(video_path)

def extract_frames(
    video_path: Union[str, Path],
    interval_seconds: float = 3.0,
    output_dir: Optional[Union[str, Path]] = None
) -> List[Dict[str, Any]]:
    """Helper wrapper function to extract frames from a video."""
    return get_video_service().extract_frames(video_path, interval_seconds, output_dir)
