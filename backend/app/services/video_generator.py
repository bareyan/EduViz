"""
Video Generator - Creates 3Blue1Brown style animations using Manim
"""

import os
import json
import asyncio
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid

from .job_manager import JobManager, JobStatus
from .tts_engine import TTSEngine
from .script_generator import ScriptGenerator
from .manim_scenes import ManimSceneBuilder


@dataclass
class VideoSegment:
    """A segment of the final video"""
    scene_file: str
    audio_file: str
    duration: float
    chapter_title: str


class VideoGenerator:
    """Generates educational videos with Manim animations and TTS"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.tts_engine = TTSEngine()
        self.script_generator = ScriptGenerator()
        self.scene_builder = ManimSceneBuilder()
    
    async def generate(
        self,
        job_id: str,
        file_id: str,
        analysis_id: str,
        selected_topics: List[int],
        style: str,
        max_video_length: int,
        voice: str,
        job_manager: JobManager,
        upload_dir: str
    ):
        """Main video generation pipeline"""
        
        try:
            # Update job status
            job_manager.update_job(
                job_id,
                status=JobStatus.GENERATING_SCRIPT,
                progress=0.1,
                message="Generating video script..."
            )
            
            # Load analysis results (in real app, would load from storage)
            # For now, we'll regenerate based on file
            file_path = self._find_file(file_id, upload_dir)
            if not file_path:
                raise FileNotFoundError(f"Source file not found: {file_id}")
            
            # Generate script for selected topics
            scripts = await self.script_generator.generate_scripts(
                file_path,
                selected_topics,
                max_video_length
            )
            
            job_manager.update_job(
                job_id,
                status=JobStatus.CREATING_ANIMATIONS,
                progress=0.3,
                message="Creating Manim animations..."
            )
            
            # Generate videos for each topic
            generated_videos = []
            total_topics = len(scripts)
            
            for i, script in enumerate(scripts):
                progress = 0.3 + (0.6 * (i / total_topics))
                job_manager.update_job(
                    job_id,
                    progress=progress,
                    message=f"Generating video {i+1}/{total_topics}: {script['title']}"
                )
                
                video = await self._generate_single_video(
                    script,
                    voice,
                    style,
                    job_id,
                    i
                )
                generated_videos.append(video)
            
            job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=1.0,
                message="All videos generated successfully!",
                result=generated_videos
            )
            
        except Exception as e:
            job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                message=f"Generation failed: {str(e)}",
                error=str(e)
            )
            raise
    
    async def _generate_single_video(
        self,
        script: Dict[str, Any],
        voice: str,
        style: str,
        job_id: str,
        index: int
    ) -> Dict[str, Any]:
        """Generate a single video from a script"""
        
        video_id = f"{job_id}_video_{index}"
        segments = []
        chapters = []
        current_time = 0.0
        
        # Process each chapter in the script
        for chapter in script.get("chapters", []):
            chapter_start = current_time
            
            # Generate TTS audio for narration
            audio_file = os.path.join(self.output_dir, f"{video_id}_{chapter['id']}_audio.mp3")
            audio_duration = await self.tts_engine.synthesize(
                chapter["narration"],
                audio_file,
                voice
            )
            
            # Generate Manim scene
            scene_file = os.path.join(self.output_dir, f"{video_id}_{chapter['id']}_scene.mp4")
            await self.scene_builder.build_scene(
                chapter["animations"],
                scene_file,
                audio_duration,
                style
            )
            
            segments.append(VideoSegment(
                scene_file=scene_file,
                audio_file=audio_file,
                duration=audio_duration,
                chapter_title=chapter["title"]
            ))
            
            chapters.append({
                "title": chapter["title"],
                "start_time": chapter_start,
                "end_time": chapter_start + audio_duration
            })
            
            current_time += audio_duration
        
        # Compose final video
        final_video_path = os.path.join(self.output_dir, f"{video_id}.mp4")
        await self._compose_video(segments, final_video_path)
        
        # Generate thumbnail
        thumbnail_path = os.path.join(self.output_dir, f"{video_id}_thumb.png")
        await self._generate_thumbnail(final_video_path, thumbnail_path)
        
        return {
            "video_id": video_id,
            "title": script["title"],
            "duration": current_time,
            "chapters": chapters,
            "download_url": f"/outputs/{video_id}.mp4",
            "thumbnail_url": f"/outputs/{video_id}_thumb.png"
        }
    
    async def _compose_video(self, segments: List[VideoSegment], output_path: str):
        """Compose video segments with audio using FFmpeg"""
        
        if not segments:
            raise ValueError("No segments to compose")
        
        # Create a temporary file list for FFmpeg concat
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for segment in segments:
                # First, merge audio with video for each segment
                merged = segment.scene_file.replace('.mp4', '_merged.mp4')
                await self._merge_audio_video(
                    segment.scene_file,
                    segment.audio_file,
                    merged
                )
                f.write(f"file '{merged}'\n")
            concat_file = f.name
        
        try:
            # Concatenate all segments
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c', 'copy',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
        finally:
            os.unlink(concat_file)
    
    async def _merge_audio_video(self, video_path: str, audio_path: str, output_path: str):
        """Merge audio track with video"""
        
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
    
    async def _generate_thumbnail(self, video_path: str, thumbnail_path: str):
        """Generate a thumbnail from the video"""
        
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-ss', '00:00:05',
            '-vframes', '1',
            '-q:v', '2',
            thumbnail_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
    
    def _find_file(self, file_id: str, upload_dir: str) -> Optional[str]:
        """Find uploaded file by ID"""
        
        for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]:
            path = os.path.join(upload_dir, f"{file_id}{ext}")
            if os.path.exists(path):
                return path
        return None
