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

    def transcribe_audio(self, audio_path: str, video_id: str) -> List[Dict]:
        """Transcribe audio using Whisper and return segments with timestamps."""
        try:
            logger.info(f"Starting transcription for {video_id}")
            self.processing_status[video_id] = {
                "status": "transcribing",
                "progress": 50
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

            logger.info(f"Transcription complete: {len(segments)} segments")

            # Save transcription to file for backup
            transcript_path = self.temp_dir / f"{video_id}_transcript.json"
            with open(transcript_path, "w") as f:
                json.dump(segments, f, indent=2)

            return segments

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
                "status": "processing",
                "progress": 10
            }

            # Get video duration
            duration = self.get_video_duration(video_path)

            # Extract audio
            self.processing_status[video_id]["progress"] = 30
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
                "total_segments": len(segments)
            }

            return segments, duration

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            self.processing_status[video_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e)
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
