import os
import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, List, Dict, Any, Optional
from PIL import Image
import av

from app.core.config import settings
from app.core.vision import describe_image

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


class VisionCaptionFrameProcessor(FrameProcessor):
    """
    Frame processor that uses the Vision Service to generate natural language captions
    for each extracted frame.
    """
    def process_frame(self, frame_data: Dict[str, Any], image: Image.Image) -> Dict[str, Any]:
        logger.info(f"Generating caption for frame {frame_data['frame_number']} (timestamp: {frame_data['timestamp']:.2f}s)...")
        try:
            # Reuses describe_image from vision.py
            caption = describe_image(image)
            logger.info(f"Successfully generated caption for frame {frame_data['frame_number']}: {caption}")
            return {"caption": caption}
        except Exception as e:
            logger.error(f"Failed to generate caption for frame {frame_data['frame_number']}: {str(e)}")
            # Handle failures gracefully by returning an error message for this frame and allowing the rest to continue
            return {"caption": f"Error: Caption generation failed: {str(e)}"}


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

    def describe_video(
        self,
        video_path: Union[str, Path],
        interval_seconds: float = 3.0,
        output_dir: Optional[Union[str, Path]] = None,
        cleanup: bool = True
    ) -> Dict[str, Any]:
        """
        Extracts frames and generates captions for each frame sequentially.
        Optionally cleans up frame image files after captioning completes.
        """
        import time
        start_time = time.time()
        
        # Ensure VisionCaptionFrameProcessor is registered
        has_caption_processor = any(
            isinstance(p, VisionCaptionFrameProcessor) for p in self._frame_processors
        )
        if not has_caption_processor:
            self.register_frame_processor(VisionCaptionFrameProcessor())
            
        video_file = Path(video_path)
        logger.info(f"Starting video description pipeline for: {video_file.name}")
        
        # Determine output path for temporary storage
        if output_dir is None:
            video_id = video_file.stem
            temp_path = Path(settings.UPLOAD_DIR) / "temp" / "video_processing" / video_id
        else:
            temp_path = Path(output_dir)
            
        try:
            # Step 1: Extract frames (which automatically triggers the caption processor)
            raw_frames = self.extract_frames(
                video_path=video_file,
                interval_seconds=interval_seconds,
                output_dir=temp_path
            )
            
            # Step 2: Format the structured result
            formatted_frames = []
            for f in raw_frames:
                formatted_frames.append({
                    "frame_number": f["frame_number"],
                    "timestamp": f["timestamp"],
                    "filename": f["filename"],
                    "caption": f.get("caption", "Error: Caption missing")
                })
                
            elapsed_time = time.time() - start_time
            logger.info(f"Video description pipeline completed in {elapsed_time:.2f}s for {video_file.name}")
            
            return {
                "frames": formatted_frames
            }
        finally:
            if cleanup:
                logger.info(f"Cleaning up temporary frame directory: {temp_path}")
                self.cleanup_directory(temp_path)

    def process_video_multimodal(
        self,
        video_path: Union[str, Path],
        interval_seconds: float = 3.0
    ) -> Dict[str, Any]:
        """
        Processes a video file, extracting visual frame captions and spoken audio
        transcripts to merge them into a single chronological timeline.
        """
        import time
        start_time = time.time()
        
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")
            
        logger.info(f"Starting multimodal video processing for: {video_file.name}")
        
        # Determine temporary directories
        video_id = video_file.stem
        temp_dir = Path(settings.UPLOAD_DIR) / "temp" / "video_processing" / video_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_audio_path = temp_dir / f"{video_id}_extracted.wav"
        
        transcript = ""
        speech_segments = []
        frames = []
        
        # Step 1: Speech Processing (Audio extraction + transcription)
        audio_success = False
        try:
            logger.info("Attempting audio extraction...")
            audio_extracted = extract_audio(video_file, temp_audio_path)
            if audio_extracted and temp_audio_path.exists():
                logger.info("Audio track extracted successfully. Running transcription...")
                transcript, speech_segments = transcribe_audio_track(temp_audio_path)
                audio_success = True
                logger.info(f"Transcription completed successfully. Word count: {len(transcript.split())}")
            else:
                logger.error("Audio extraction failed or file not found. Skipping speech understanding.")
        except Exception as e:
            logger.error(f"Audio transcription pipeline failed: {str(e)}", exc_info=True)
            # Fail gracefully, continue with vision only
            transcript = ""
            speech_segments = []
            
        # Step 2: Vision Processing (Frame extraction + Florence-2 captioning)
        vision_success = False
        try:
            logger.info("Running visual frame extraction and captioning...")
            vision_result = self.describe_video(
                video_path=video_file,
                interval_seconds=interval_seconds,
                output_dir=temp_dir / "frames",
                cleanup=True  # Automatically cleans up frame jpg files
            )
            frames = vision_result.get("frames", [])
            vision_success = True
            logger.info(f"Visual processing completed successfully. Frame count: {len(frames)}")
        except Exception as e:
            logger.error(f"Visual processing pipeline failed: {str(e)}", exc_info=True)
            # Fail gracefully, continue with audio only
            frames = []
            
        # Raise exception if BOTH pipelines failed
        if not audio_success and not vision_success:
            logger.critical("Both audio and vision processing pipelines failed.")
            raise RuntimeError("Multimodal video processing failed completely: both audio and vision pipelines encountered errors.")
            
        # Step 3: Chronological Timeline Merging
        logger.info("Merging speech and visual segments into timeline...")
        timeline = merge_timeline(frames, speech_segments)
        
        # Cleanup temp audio file
        try:
            if temp_audio_path.exists():
                temp_audio_path.unlink()
            if temp_dir.exists() and not os.listdir(temp_dir):
                # Delete directory if empty
                temp_dir.rmdir()
        except Exception as ce:
            logger.warning(f"Failed to clean up temporary audio directory: {str(ce)}")
            
        total_time = time.time() - start_time
        logger.info(f"Multimodal processing completed for {video_file.name} in {total_time:.2f}s")
        
        return {
            "transcript": transcript,
            "frames": frames,
            "timeline": timeline
        }


def extract_audio(video_path: Path, output_audio_path: Path) -> bool:
    """
    Extracts the audio track from a video file using FFmpeg.
    """
    logger.info(f"Extracting audio track from {video_path.name} to {output_audio_path.name}")
    import static_ffmpeg
    static_ffmpeg.add_paths()
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(output_audio_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        logger.error(f"FFmpeg audio extraction failed: {str(e)}")
        return False


def transcribe_audio_track(audio_path: Path) -> tuple[str, list[dict]]:
    """
    Transcribes an audio file using the cached faster-whisper model.
    """
    from app.api.v1.endpoints.audio import get_whisper_model
    logger.info(f"Transcribing audio track: {audio_path.name}")
    model = get_whisper_model()
    segments, info = model.transcribe(str(audio_path), language="en", task="transcribe")
    segments_list = list(segments)
    
    transcript = " ".join([segment.text for segment in segments_list]).strip()
    
    timeline_segments = []
    for seg in segments_list:
        timeline_segments.append({
            "start": round(float(seg.start), 2),
            "end": round(float(seg.end), 2),
            "text": seg.text.strip()
        })
    return transcript, timeline_segments


def merge_timeline(frames: list[dict], speech_segments: list[dict]) -> list[dict]:
    """
    Combines speech segments and visual frame captions chronologically.
    """
    timeline = []
    for f in frames:
        timeline.append({
            "timestamp": round(f["timestamp"], 2),
            "type": "vision",
            "content": f.get("caption", "")
        })
    for s in speech_segments:
        timeline.append({
            "timestamp": round(s["start"], 2),
            "type": "speech",
            "content": s.get("text", "")
        })
    # Sort chronologically by timestamp, placing vision events before speech events if timestamps align
    timeline.sort(key=lambda x: (x["timestamp"], x["type"]))
    return timeline


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

def describe_video(
    video_path: Union[str, Path],
    interval_seconds: float = 3.0,
    output_dir: Optional[Union[str, Path]] = None,
    cleanup: bool = True
) -> Dict[str, Any]:
    """Helper wrapper function to describe all extracted frames of a video."""
    return get_video_service().describe_video(video_path, interval_seconds, output_dir, cleanup)

def process_video_multimodal(
    video_path: Union[str, Path],
    interval_seconds: float = 3.0
) -> Dict[str, Any]:
    """Helper wrapper function to perform unified chronological multimodal audio/vision understanding on a video."""
    return get_video_service().process_video_multimodal(video_path, interval_seconds)
