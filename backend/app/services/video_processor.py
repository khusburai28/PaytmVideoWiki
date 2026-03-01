import os
import whisper
import ffmpeg
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self, upload_dir: str = "./uploads", temp_dir: str = "./temp", whisper_model: str = "base"):
        self.upload_dir = Path(upload_dir)
        self.temp_dir = Path(temp_dir)
        self.upload_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

        logger.info(f"Loading Whisper model: {whisper_model}")
        self.whisper_model = whisper.load_model(whisper_model)

        # Store processing status
        self.processing_status: Dict[str, Dict] = {}

    def save_video(self, file_content: bytes, filename: str) -> tuple[str, str]:
        """Save uploaded video and return video_id and path."""
        video_id = str(uuid.uuid4())
        file_extension = Path(filename).suffix
        video_path = self.upload_dir / f"{video_id}{file_extension}"

        with open(video_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Video saved: {video_id} ({filename})")
        return video_id, str(video_path)

    def extract_audio(self, video_path: str, video_id: str) -> str:
        """Extract audio from video using ffmpeg."""
        audio_path = self.temp_dir / f"{video_id}.wav"

        try:
            logger.info(f"Extracting audio from {video_path}")
            self.processing_status[video_id] = {
                "status": "extracting_audio",
                "progress": 20,
                "message": "Extracting audio from video..."
            }
            (
                ffmpeg
                .input(video_path)
                .output(str(audio_path), acodec='pcm_s16le', ac=1, ar='16k')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, quiet=True)
            )
            logger.info(f"Audio extracted to {audio_path}")
            return str(audio_path)
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise Exception(f"Failed to extract audio: {e.stderr.decode()}")

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        try:
            probe = ffmpeg.probe(video_path)
            duration = float(probe['streams'][0]['duration'])
            return duration
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            return 0.0

    def merge_small_segments(self, segments: List[Dict], min_duration: float = 30.0) -> List[Dict]:
        """Merge small segments to create larger, more meaningful chunks with inline timestamps."""
        if not segments:
            return []

        def format_timestamp(seconds: float) -> str:
            """Format seconds to MM:SS or HH:MM:SS."""
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"

        merged = []
        current_segments = [segments[0]]  # Track individual segments within chunk

        for segment in segments[1:]:
            chunk_start = current_segments[0]['start_time']
            chunk_end = current_segments[-1]['end_time']
            chunk_duration = chunk_end - chunk_start
            chunk_text_length = sum(len(s['text']) for s in current_segments)

            # Merge if current chunk is too short or text is too brief
            if chunk_duration < min_duration or chunk_text_length < 100:
                current_segments.append(segment)
            else:
                # Finalize current chunk with inline timestamps
                chunk_text_parts = []
                for seg in current_segments:
                    timestamp = format_timestamp(seg['start_time'])
                    chunk_text_parts.append(f"[{timestamp}] {seg['text']}")

                merged.append({
                    "text": " ".join(chunk_text_parts),
                    "start_time": current_segments[0]['start_time'],
                    "end_time": current_segments[-1]['end_time'],
                    "confidence": sum(s.get('confidence', 0.0) for s in current_segments) / len(current_segments)
                })

                # Start new chunk
                current_segments = [segment]

        # Add the last chunk with inline timestamps
        if current_segments:
            chunk_text_parts = []
            for seg in current_segments:
                timestamp = format_timestamp(seg['start_time'])
                chunk_text_parts.append(f"[{timestamp}] {seg['text']}")

            merged.append({
                "text": " ".join(chunk_text_parts),
                "start_time": current_segments[0]['start_time'],
                "end_time": current_segments[-1]['end_time'],
                "confidence": sum(s.get('confidence', 0.0) for s in current_segments) / len(current_segments)
            })

        logger.info(f"Merged {len(segments)} segments into {len(merged)} chunks (min duration: {min_duration}s)")
        return merged

    def transcribe_audio(self, audio_path: str, video_id: str) -> List[Dict]:
        """Transcribe audio using Whisper and return segments with timestamps."""
        try:
            logger.info(f"Starting transcription for {video_id}")
            self.processing_status[video_id] = {
                "status": "transcribing",
                "progress": 40,
                "message": "Transcribing audio with Whisper AI..."
            }

            result = self.whisper_model.transcribe(
                audio_path,
                word_timestamps=False,
                verbose=False
            )

            segments = []
            for segment in result['segments']:
                segments.append({
                    "text": segment['text'].strip(),
                    "start_time": segment['start'],
                    "end_time": segment['end'],
                    "confidence": segment.get('confidence', 0.0)
                })

            logger.info(f"Transcription complete: {len(segments)} raw segments")

            # Update status for merging
            self.processing_status[video_id] = {
                "status": "processing_segments",
                "progress": 70,
                "message": "Processing and merging transcript segments..."
            }

            # Merge small segments into larger chunks (30 seconds minimum)
            merged_segments = self.merge_small_segments(segments, min_duration=30.0)

            # Save transcription to file for backup
            transcript_path = self.temp_dir / f"{video_id}_transcript.json"
            with open(transcript_path, "w") as f:
                json.dump(merged_segments, f, indent=2)

            return merged_segments

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            self.processing_status[video_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e)
            }
            raise

    def process_video(self, video_path: str, video_id: str) -> tuple[List[Dict], float]:
        """Complete video processing pipeline."""
        try:
            self.processing_status[video_id] = {
                "status": "initializing",
                "progress": 10,
                "message": "Initializing video processing..."
            }

            # Get video duration
            duration = self.get_video_duration(video_path)

            # Extract audio
            audio_path = self.extract_audio(video_path, video_id)

            # Transcribe
            segments = self.transcribe_audio(audio_path, video_id)

            # Cleanup audio file
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp audio file: {e}")

            self.processing_status[video_id] = {
                "status": "completed",
                "progress": 100,
                "total_segments": len(segments),
                "message": "Video processing completed successfully!"
            }

            return segments, duration

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            self.processing_status[video_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e),
                "message": f"Processing failed: {str(e)}"
            }
            raise

    def get_status(self, video_id: str) -> Optional[Dict]:
        """Get processing status for a video."""
        return self.processing_status.get(video_id)

    def cleanup_video(self, video_id: str):
        """Remove video and associated files."""
        try:
            # Remove video file
            for file in self.upload_dir.glob(f"{video_id}.*"):
                file.unlink()

            # Remove transcript
            transcript_file = self.temp_dir / f"{video_id}_transcript.json"
            if transcript_file.exists():
                transcript_file.unlink()

            # Remove from status
            if video_id in self.processing_status:
                del self.processing_status[video_id]

            logger.info(f"Cleaned up video: {video_id}")
        except Exception as e:
            logger.error(f"Cleanup failed for {video_id}: {e}")
