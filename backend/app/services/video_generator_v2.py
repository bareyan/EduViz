"""
Video Generator V2 - Orchestrates the complete video generation pipeline
Generates videos section-by-section with proper audio sync
"""

import os
import asyncio
import subprocess
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from .analyzer_v2 import MaterialAnalyzer
from .script_generator_v2 import ScriptGenerator
from .manim_generator import ManimGenerator
from .tts_engine import TTSEngine


class VideoGenerator:
    """Orchestrates the complete video generation pipeline"""
    
    def __init__(self, output_base_dir: str):
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.analyzer = MaterialAnalyzer()
        self.script_generator = ScriptGenerator()
        self.manim_generator = ManimGenerator()
        self.tts_engine = TTSEngine()
    
    async def generate_video(
        self,
        file_path: str,
        file_id: str,
        topic: Dict[str, Any],
        voice: str = "en-US-GuyNeural",
        progress_callback: Optional[callable] = None,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a complete video for a topic"""
        
        # Debug logging
        print(f"[VideoGenerator] Starting video generation")
        print(f"[VideoGenerator] File path: {file_path}")
        print(f"[VideoGenerator] File exists: {os.path.exists(file_path)}")
        print(f"[VideoGenerator] Topic: {topic.get('title', 'Unknown')}")
        
        # Create job directory - use provided job_id or generate one
        if not job_id:
            job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_id}"
        job_dir = self.output_base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        sections_dir = job_dir / "sections"
        sections_dir.mkdir(exist_ok=True)
        
        try:
            # Step 1: Generate the script
            if progress_callback:
                progress_callback({"stage": "script", "progress": 0, "message": "Generating script..."})
            
            print(f"[VideoGenerator] Calling script generator with file: {file_path}")
            
            script = await self.script_generator.generate_script(
                file_path=file_path,
                topic=topic,
                max_duration_minutes=topic.get("estimated_duration_minutes", 15)
            )
            
            print(f"[VideoGenerator] Script generated with {len(script.get('sections', []))} sections")
            print(f"[VideoGenerator] Script title: {script.get('title', 'No title')}")
            
            # Save script for reference
            script_path = job_dir / "script.json"
            import json
            with open(script_path, "w") as f:
                json.dump(script, f, indent=2)
            
            sections = script.get("sections", [])
            total_sections = len(sections)
            
            if progress_callback:
                progress_callback({"stage": "script", "progress": 100, "message": f"Script generated with {total_sections} sections"})
            
            # Step 2: Generate audio and video for each section in parallel
            section_videos = []
            section_audios = []
            chapters = []
            current_time = 0
            
            # Limit concurrent processing to avoid overwhelming system
            # Manim rendering is CPU-intensive, so limit to reasonable parallelism
            max_concurrent = min(16, os.cpu_count() or 2)  # Max 8 concurrent, or CPU count
            semaphore = asyncio.Semaphore(max_concurrent)
            
            # Track progress across parallel tasks
            completed_count = [0]  # Use list for mutability in closure
            
            # Process sections in parallel for faster generation
            async def process_section(i: int, section: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single section - generates audio and video"""
                async with semaphore:  # Limit concurrency
                    section_id = section.get("id", f"section_{i}")
                    section_dir = sections_dir / section_id
                    section_dir.mkdir(exist_ok=True)
                    
                    print(f"[Parallel] Starting section {i + 1}/{total_sections}: {section.get('title', '')}")
                    
                    result = {
                        "index": i,
                        "video_path": None,
                        "audio_path": None,
                        "duration": section.get("duration_seconds", 30),
                        "title": section.get("title", f"Section {i + 1}")
                    }
                    
                    # Generate audio for this section FIRST
                    # Use tts_narration (spoken version) if available, fall back to narration
                    tts_text = section.get("tts_narration") or section.get("narration", "")
                    
                    # Clean narration for TTS - remove pause markers that would be spoken
                    clean_narration = self._clean_narration_for_tts(tts_text)
                    
                    audio_path = section_dir / "audio.mp3"
                    audio_duration = section.get("duration_seconds", 60)  # Default estimate
                    
                    try:
                        await self.tts_engine.generate_speech(
                            text=clean_narration,
                            output_path=str(audio_path),
                            voice=voice
                        )
                        
                        # Get actual audio duration - this is the key timing reference
                        audio_duration = await self._get_audio_duration(str(audio_path))
                        section["actual_duration"] = audio_duration
                        result["duration"] = audio_duration
                        result["audio_path"] = str(audio_path)
                        print(f"Section {i} audio duration: {audio_duration:.1f}s")
                        
                    except Exception as e:
                        print(f"TTS error for section {i}: {e}")
                        audio_path = None
                    
                    # Generate Manim video for this section, using audio duration for timing
                    try:
                        manim_result = await self.manim_generator.generate_section_video(
                            section=section,
                            output_dir=str(section_dir),
                            section_index=i,
                            audio_duration=audio_duration  # Pass audio duration for sync
                        )
                        video_path = manim_result.get("video_path") if isinstance(manim_result, dict) else manim_result
                        if video_path and os.path.exists(video_path):
                            result["video_path"] = video_path
                        # Store manim_code in section for persistence
                        if isinstance(manim_result, dict) and manim_result.get("manim_code"):
                            section["manim_code"] = manim_result["manim_code"]
                            result["manim_code"] = manim_result["manim_code"]
                    except Exception as e:
                        print(f"Manim error for section {i}: {e}")
                    
                    # Update progress after completing each section
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback({
                            "stage": "sections",
                            "progress": int((completed_count[0] / total_sections) * 100),
                            "message": f"Completed section {completed_count[0]}/{total_sections}"
                        })
                    
                    print(f"[Parallel] Finished section {i + 1}/{total_sections}")
                    return result
            
            # Report progress and run sections in parallel
            if progress_callback:
                progress_callback({
                    "stage": "sections",
                    "progress": 0,
                    "message": f"Processing {total_sections} sections in parallel (max {max_concurrent} concurrent)..."
                })
            
            # Run all sections in parallel (with semaphore limiting concurrency)
            section_tasks = [
                process_section(i, section) 
                for i, section in enumerate(sections)
            ]
            section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
            
            # Process results in order and update sections with video/audio paths
            for i, result in enumerate(section_results):
                if isinstance(result, Exception):
                    print(f"Section {i} processing error: {result}")
                    continue
                
                # Store section order/index for correct chronological display
                if i < len(sections):
                    sections[i]["order"] = i
                
                video_path = result.get("video_path")
                audio_path = result.get("audio_path")
                
                # CRITICAL: Only add to combine lists if BOTH video and audio exist
                # This prevents misalignment when a section fails to generate video
                if video_path and audio_path:
                    section_videos.append(video_path)
                    section_audios.append(audio_path)
                    # Store paths in section for edit page
                    if i < len(sections):
                        sections[i]["video"] = video_path
                        sections[i]["audio"] = audio_path
                elif video_path:
                    # Video but no audio - still include in final video
                    section_videos.append(video_path)
                    section_audios.append(None)  # Placeholder to keep alignment
                    if i < len(sections):
                        sections[i]["video"] = video_path
                    print(f"Warning: Section {i} has video but no audio")
                elif audio_path:
                    # Audio but no video - skip this section in final video
                    # but still store audio path for reference
                    if i < len(sections):
                        sections[i]["audio"] = audio_path
                    print(f"Warning: Section {i} has audio but no video - SKIPPING from final video")
                else:
                    print(f"Warning: Section {i} has neither video nor audio - SKIPPING")
                    continue
                    
                # Store manim_code if present in result
                if result.get("manim_code") and i < len(sections):
                    sections[i]["manim_code"] = result["manim_code"]
                
                # Track chapter timing (only for sections with video)
                if video_path:
                    chapters.append({
                        "title": result["title"],
                        "start_time": current_time,
                        "duration": result["duration"]
                    })
                    current_time += result["duration"]
            
            if progress_callback:
                progress_callback({"stage": "sections", "progress": 100, "message": "All sections processed"})
            
            # Save updated script.json with manim_code for each section
            script_path = job_dir / "script.json"
            with open(script_path, "w") as f:
                json.dump(script, f, indent=2)
            print(f"Saved updated script.json with manim_code for {len(sections)} sections")
            
            # Step 3: Combine sections into final video
            if progress_callback:
                progress_callback({"stage": "combining", "progress": 0, "message": "Combining sections..."})
            
            final_video_path = job_dir / "final_video.mp4"
            
            if section_videos and section_audios:
                await self._combine_sections(
                    videos=section_videos,
                    audios=section_audios,
                    output_path=str(final_video_path),
                    sections_dir=str(sections_dir)
                )
            elif section_videos:
                # Just concatenate videos without audio
                await self._concatenate_videos(section_videos, str(final_video_path))
            else:
                raise ValueError("No video sections were generated")
            
            if progress_callback:
                progress_callback({"stage": "combining", "progress": 100, "message": "Video complete!"})
            
            # Step 4: Cleanup intermediate files (but KEEP scene .py files)
            await self._cleanup_intermediate_files(sections_dir)
            
            return {
                "job_id": job_id,
                "video_path": str(final_video_path),
                "script": script,
                "chapters": chapters,
                "total_duration": current_time,
                "status": "completed"
            }
            
        except Exception as e:
            print(f"Video generation error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "job_id": job_id,
                "error": str(e),
                "status": "failed"
            }
    
    async def _cleanup_intermediate_files(self, sections_dir: Path):
        """Remove intermediate files after successful generation - KEEP scene files and section videos for editing"""
        try:
            import shutil
            for section_path in sections_dir.iterdir():
                if section_path.is_dir():
                    # KEEP:
                    # - Python scene files (.py) for later editing
                    # - Section videos (.mp4) for preview in edit page
                    # - Audio files (.mp3) for recompilation
                    
                    # Only remove the media/videos folders created by manim (temporary render intermediates)
                    # These contain partial renders, not the final section videos
                    media_dir = section_path / "media"
                    if media_dir.exists():
                        shutil.rmtree(media_dir)
                    # Remove fallback files (these are just backup attempts during error correction)
                    for f in section_path.glob("fallback_*.py"):
                        f.unlink()
                    # Remove __pycache__ folders
                    pycache_dir = section_path / "__pycache__"
                    if pycache_dir.exists():
                        shutil.rmtree(pycache_dir)
            print("Cleaned up intermediate files (preserved .py, .mp4, .mp3 files)")
        except Exception as e:
            print(f"Cleanup error (non-fatal): {e}")
    
    def _clean_narration_for_tts(self, narration: str) -> str:
        """Clean narration text for TTS - remove pause markers that would be spoken"""
        import re
        
        # Remove [PAUSE] markers
        clean = re.sub(r'\[PAUSE\]', '', narration)
        
        # Remove standalone "..." (but keep as natural pause in speech)
        # Replace "..." with a comma for natural TTS pacing
        clean = re.sub(r'\s*\.\.\.\s*', ', ', clean)
        
        # Remove [CALCULATION] markers
        clean = re.sub(r'\[CALCULATION\]', '', clean)
        
        # Remove other bracket markers like [something]
        clean = re.sub(r'\[[^\]]*\]', '', clean)
        
        # Clean up multiple spaces and commas
        clean = re.sub(r',\s*,', ',', clean)
        clean = re.sub(r'\s+', ' ', clean)
        
        # Clean up leading/trailing commas in sentences
        clean = re.sub(r',\s*\.', '.', clean)
        clean = re.sub(r'^\s*,\s*', '', clean)
        
        return clean.strip()
    
    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ]
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 30.0  # Default duration
    
    async def _generate_silence(self, output_path: str, duration: float) -> None:
        """Generate a silent audio file of specified duration"""
        try:
            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo",
                "-t", str(duration),
                "-q:a", "9",
                "-y",
                output_path
            ]
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                check=True
            )
            print(f"Generated {duration:.1f}s silence: {output_path}")
        except Exception as e:
            print(f"Silence generation failed: {e}")
            raise
    
    async def _combine_sections(
        self,
        videos: List[str],
        audios: List[str],  # May contain None for sections without audio
        output_path: str,
        sections_dir: str
    ):
        """Combine video sections with their audio"""
        
        # First, merge each video with its audio
        merged_sections = []
        
        for i, (video, audio) in enumerate(zip(videos, audios)):
            merged_path = Path(sections_dir) / f"merged_{i}.mp4"
            
            if audio is None:
                # No audio for this section - just copy the video
                print(f"Section {i}: No audio, using video as-is")
                merged_sections.append(video)
                continue
            
            # Simpler approach: just overlay audio on video
            cmd = [
                "ffmpeg", "-y",
                "-i", video,
                "-i", audio,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                str(merged_path)
            ]
            
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    timeout=120
                )
                if merged_path.exists():
                    merged_sections.append(str(merged_path))
            except Exception as e:
                print(f"Error merging section {i}: {e}")
                # Use original video if merge fails
                merged_sections.append(video)
        
        # Now concatenate all merged sections
        if merged_sections:
            await self._concatenate_videos(merged_sections, output_path)
    
    async def _concatenate_videos(self, videos: List[str], output_path: str):
        """Concatenate multiple videos into one"""
        
        if not videos:
            return
        
        if len(videos) == 1:
            shutil.copy(videos[0], output_path)
            return
        
        # Create concat file
        concat_file = Path(output_path).parent / "concat_list.txt"
        with open(concat_file, "w") as f:
            for video in videos:
                f.write(f"file '{video}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            output_path
        ]
        
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"Concat error: {result.stderr}")
                # Try re-encoding
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    output_path
                ]
                await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    timeout=300
                )
        except Exception as e:
            print(f"Concatenation error: {e}")
