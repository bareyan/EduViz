"""
Video Generator V2 - Orchestrates the complete video generation pipeline
Generates videos section-by-section with proper audio sync
"""

import os
import json
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
        job_id: Optional[str] = None,
        video_mode: str = "comprehensive",  # "comprehensive" or "overview"
        style: str = "3b1b",  # "3b1b" (dark) or "clean" (light)
        language: str = "en"  # Language code for content generation
    ) -> Dict[str, Any]:
        """Generate a complete video for a topic
        
        Args:
            file_path: Path to the source file
            file_id: Unique identifier for the file
            topic: Topic data with title, description, etc.
            voice: TTS voice to use
            progress_callback: Callback for progress updates
            job_id: Optional job ID for the output folder
            video_mode: "comprehensive" for detailed videos, "overview" for quick summaries
            style: Visual style - "3b1b" for dark theme, "clean" for light theme
            language: Language code for content generation (en, fr, etc.)
        """
        
        # Debug logging
        print(f"[VideoGenerator] Starting video generation")
        print(f"[VideoGenerator] File path: {file_path}")
        print(f"[VideoGenerator] File exists: {os.path.exists(file_path)}")
        print(f"[VideoGenerator] Topic: {topic.get('title', 'Unknown')}")
        print(f"[VideoGenerator] Video mode: {video_mode}")
        print(f"[VideoGenerator] Language: {language}")
        
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
                progress_callback({"stage": "script", "progress": 0, "message": f"Generating {video_mode} script..."})
            
            print(f"[VideoGenerator] Calling script generator with file: {file_path}")
            
            script = await self.script_generator.generate_script(
                file_path=file_path,
                topic=topic,
                max_duration_minutes=topic.get("estimated_duration_minutes", 15),
                video_mode=video_mode,
                language=language
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
            # Uses subsection sync points for better audio-video alignment
            section_videos = []
            section_audios = []
            chapters = []
            current_time = 0
            
            # Target subsection duration for sync points (30-45 seconds for longer videos)
            TARGET_SUBSECTION_DURATION = 35  # seconds - sweet spot for sync
            MAX_SUBSECTION_DURATION = 50  # Never exceed this
            
            # Limit concurrent processing to avoid overwhelming system
            # Manim rendering is CPU-intensive, so limit to reasonable parallelism
            max_concurrent = min(8, os.cpu_count() or 2)  # Max 8 concurrent, or CPU count
            semaphore = asyncio.Semaphore(max_concurrent)
            
            # Track progress across parallel tasks
            completed_count = [0]  # Use list for mutability in closure
            
            # Process sections in parallel for faster generation
            async def process_section(i: int, section: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single section - divides into subsections for sync, generates audio+video for each"""
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
                    
                    # Get narration text
                    tts_text = section.get("tts_narration") or section.get("narration", "")
                    clean_narration = self._clean_narration_for_tts(tts_text)
                    
                    # Divide section into subsections at natural breakpoints
                    subsections = self._divide_into_subsections(
                        narration=clean_narration,
                        visual_description=section.get("visual_description", ""),
                        target_duration=TARGET_SUBSECTION_DURATION,
                        max_duration=MAX_SUBSECTION_DURATION
                    )
                    
                    print(f"Section {i}: Divided into {len(subsections)} subsections for sync")
                    
                    if len(subsections) <= 1:
                        # Simple case: single subsection, use original flow
                        subsection_results = await self._process_single_subsection(
                            section=section,
                            narration=clean_narration,
                            section_dir=section_dir,
                            section_index=i,
                            voice=voice,
                            style=style
                        )
                        result["video_path"] = subsection_results.get("video_path")
                        result["audio_path"] = subsection_results.get("audio_path")
                        result["duration"] = subsection_results.get("duration", 30)
                        if subsection_results.get("manim_code"):
                            section["manim_code"] = subsection_results["manim_code"]
                            result["manim_code"] = subsection_results["manim_code"]
                    else:
                        # Multiple subsections: process each, then merge for perfect sync
                        merged_result = await self._process_subsections_with_sync(
                            section=section,
                            subsections=subsections,
                            section_dir=section_dir,
                            section_index=i,
                            voice=voice,
                            style=style
                        )
                        result["video_path"] = merged_result.get("video_path")
                        result["audio_path"] = merged_result.get("audio_path")
                        result["duration"] = merged_result.get("duration", 30)
                        if merged_result.get("manim_code"):
                            section["manim_code"] = merged_result["manim_code"]
                            result["manim_code"] = merged_result["manim_code"]
                    
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
    
    def _divide_into_subsections(
        self,
        narration: str,
        visual_description: str,
        target_duration: int = 20,
        max_duration: int = 30
    ) -> List[Dict[str, Any]]:
        """Divide narration into subsections at natural breakpoints for sync
        
        Uses sentence boundaries and pause markers to find optimal split points.
        Each subsection will have its own audio+video generated for perfect sync.
        
        Args:
            narration: The full narration text
            visual_description: Visual description for the section
            target_duration: Target duration per subsection in seconds
            max_duration: Maximum duration before forcing a split
            
        Returns:
            List of subsection dicts with narration and visual hints
        """
        import re
        
        if not narration or len(narration) < 100:
            # Very short narration - don't split
            return [{"narration": narration, "visual_hint": visual_description, "index": 0}]
        
        # Estimate speaking rate: ~150 words per minute = 2.5 words/second
        # Average word length ~5 chars, so ~12.5 chars/second
        CHARS_PER_SECOND = 12.5
        
        estimated_total_duration = len(narration) / CHARS_PER_SECOND
        
        if estimated_total_duration <= max_duration:
            # Section is short enough, no split needed
            return [{"narration": narration, "visual_hint": visual_description, "index": 0}]
        
        # Find natural breakpoints: sentence endings, pause markers
        # Priority: [PAUSE] markers > "..." > sentence endings (. ! ?)
        
        # Split into sentences first
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, narration)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            # Single long sentence - split at commas or just return as-is
            return [{"narration": narration, "visual_hint": visual_description, "index": 0}]
        
        # Group sentences into subsections based on target duration
        subsections = []
        current_subsection = []
        current_length = 0
        target_chars = target_duration * CHARS_PER_SECOND
        max_chars = max_duration * CHARS_PER_SECOND
        
        for sentence in sentences:
            sentence_len = len(sentence)
            
            # Check if adding this sentence would exceed max duration
            if current_length + sentence_len > max_chars and current_subsection:
                # Save current subsection and start new one
                subsection_text = " ".join(current_subsection)
                subsections.append({
                    "narration": subsection_text,
                    "visual_hint": f"Part {len(subsections) + 1} of visual: {visual_description[:200]}",
                    "index": len(subsections)
                })
                current_subsection = [sentence]
                current_length = sentence_len
            elif current_length + sentence_len > target_chars and current_subsection:
                # At target duration with content - split here for sync
                subsection_text = " ".join(current_subsection)
                subsections.append({
                    "narration": subsection_text,
                    "visual_hint": f"Part {len(subsections) + 1} of visual: {visual_description[:200]}",
                    "index": len(subsections)
                })
                current_subsection = [sentence]
                current_length = sentence_len
            else:
                # Add to current subsection
                current_subsection.append(sentence)
                current_length += sentence_len + 1  # +1 for space
        
        # Don't forget the last subsection
        if current_subsection:
            subsection_text = " ".join(current_subsection)
            subsections.append({
                "narration": subsection_text,
                "visual_hint": f"Part {len(subsections) + 1} of visual: {visual_description[:200]}",
                "index": len(subsections)
            })
        
        print(f"Divided narration ({len(narration)} chars, ~{estimated_total_duration:.0f}s) into {len(subsections)} subsections")
        return subsections
    
    async def _process_single_subsection(
        self,
        section: Dict[str, Any],
        narration: str,
        section_dir: Path,
        section_index: int,
        voice: str,
        style: str
    ) -> Dict[str, Any]:
        """Process a section with a single subsection (original flow)"""
        result = {
            "video_path": None,
            "audio_path": None,
            "duration": 30,
            "manim_code": None
        }
        
        audio_path = section_dir / "audio.mp3"
        audio_duration = section.get("duration_seconds", 60)
        
        try:
            await self.tts_engine.generate_speech(
                text=narration,
                output_path=str(audio_path),
                voice=voice
            )
            audio_duration = await self._get_audio_duration(str(audio_path))
            section["actual_duration"] = audio_duration
            result["duration"] = audio_duration
            result["audio_path"] = str(audio_path)
            print(f"Section {section_index} audio duration: {audio_duration:.1f}s")
        except Exception as e:
            print(f"TTS error for section {section_index}: {e}")
            audio_path = None
        
        try:
            manim_result = await self.manim_generator.generate_section_video(
                section=section,
                output_dir=str(section_dir),
                section_index=section_index,
                audio_duration=audio_duration,
                style=style
            )
            video_path = manim_result.get("video_path") if isinstance(manim_result, dict) else manim_result
            if video_path and os.path.exists(video_path):
                result["video_path"] = video_path
            if isinstance(manim_result, dict) and manim_result.get("manim_code"):
                result["manim_code"] = manim_result["manim_code"]
        except Exception as e:
            print(f"Manim error for section {section_index}: {e}")
        
        return result
    
    async def _process_subsections_with_sync(
        self,
        section: Dict[str, Any],
        subsections: List[Dict[str, Any]],
        section_dir: Path,
        section_index: int,
        voice: str,
        style: str
    ) -> Dict[str, Any]:
        """Process multiple subsections and merge them for perfect sync
        
        Each subsection gets its own audio+video pair generated, then they're
        merged together. This ensures sync at each subsection boundary.
        """
        result = {
            "video_path": None,
            "audio_path": None,
            "duration": 0,
            "manim_code": None
        }
        
        subsection_results = []
        all_manim_code = []
        total_duration = 0
        
        for sub_idx, subsection in enumerate(subsections):
            sub_dir = section_dir / f"sub_{sub_idx}"
            sub_dir.mkdir(exist_ok=True)
            
            sub_narration = subsection["narration"]
            sub_visual = subsection["visual_hint"]
            
            # Create a mini-section for this subsection
            mini_section = {
                "id": f"{section.get('id', 'section')}_{sub_idx}",
                "title": f"{section.get('title', 'Section')} (part {sub_idx + 1})",
                "narration": sub_narration,
                "tts_narration": sub_narration,
                "visual_description": sub_visual,
                "key_concepts": section.get("key_concepts", []),
                "animation_type": section.get("animation_type", "text"),
                "style": style,
                "is_subsection": True,
                "subsection_index": sub_idx,
                "total_subsections": len(subsections)
            }
            
            # Generate audio for this subsection
            audio_path = sub_dir / "audio.mp3"
            audio_duration = 15  # Default estimate
            
            try:
                await self.tts_engine.generate_speech(
                    text=sub_narration,
                    output_path=str(audio_path),
                    voice=voice
                )
                audio_duration = await self._get_audio_duration(str(audio_path))
                print(f"Section {section_index} sub {sub_idx}: audio duration {audio_duration:.1f}s")
            except Exception as e:
                print(f"TTS error for section {section_index} sub {sub_idx}: {e}")
                audio_path = None
            
            # Generate video for this subsection
            video_path = None
            manim_code = None
            
            try:
                manim_result = await self.manim_generator.generate_section_video(
                    section=mini_section,
                    output_dir=str(sub_dir),
                    section_index=f"{section_index}_{sub_idx}",
                    audio_duration=audio_duration,
                    style=style
                )
                video_path = manim_result.get("video_path") if isinstance(manim_result, dict) else manim_result
                if isinstance(manim_result, dict) and manim_result.get("manim_code"):
                    manim_code = manim_result["manim_code"]
                    all_manim_code.append(f"# === Subsection {sub_idx + 1} ===\n{manim_code}")
            except Exception as e:
                print(f"Manim error for section {section_index} sub {sub_idx}: {e}")
            
            if video_path and audio_path:
                subsection_results.append({
                    "video_path": video_path,
                    "audio_path": str(audio_path),
                    "duration": audio_duration
                })
                total_duration += audio_duration
        
        if not subsection_results:
            print(f"Section {section_index}: No subsections succeeded")
            return result
        
        # Merge all subsections into one section video
        if len(subsection_results) == 1:
            # Only one subsection succeeded - use it directly
            result["video_path"] = subsection_results[0]["video_path"]
            result["audio_path"] = subsection_results[0]["audio_path"]
            result["duration"] = subsection_results[0]["duration"]
        else:
            # Multiple subsections - merge them
            merged_video = await self._merge_subsections(
                subsection_results=subsection_results,
                output_dir=section_dir,
                section_index=section_index
            )
            result["video_path"] = merged_video.get("video_path")
            result["audio_path"] = merged_video.get("audio_path")
            result["duration"] = total_duration
        
        # Combine all manim code
        if all_manim_code:
            result["manim_code"] = "\n\n".join(all_manim_code)
        
        return result
    
    async def _merge_subsections(
        self,
        subsection_results: List[Dict[str, Any]],
        output_dir: Path,
        section_index: int
    ) -> Dict[str, Any]:
        """Merge subsection videos+audios into a single section video
        
        Each subsection already has matched audio+video, so we just concatenate.
        """
        # First, merge each subsection's video+audio
        merged_clips = []
        
        for sub_idx, sub_result in enumerate(subsection_results):
            video_path = sub_result["video_path"]
            audio_path = sub_result["audio_path"]
            merged_path = output_dir / f"merged_sub_{sub_idx}.mp4"
            
            # Get durations
            audio_duration = await self._get_media_duration(audio_path)
            video_duration = await self._get_media_duration(video_path)
            
            if video_duration >= audio_duration:
                # Video is long enough
                cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-i", audio_path,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-shortest",
                    str(merged_path)
                ]
            else:
                # Extend video to match audio
                cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-i", audio_path,
                    "-filter_complex", f"[0:v]tpad=stop=-1:stop_mode=clone,setpts=PTS-STARTPTS[v]",
                    "-map", "[v]",
                    "-map", "1:a:0",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-t", str(audio_duration),
                    str(merged_path)
                ]
            
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0 and merged_path.exists():
                    merged_clips.append(str(merged_path))
                else:
                    print(f"FFmpeg error merging subsection {sub_idx}: {result.stderr}")
            except Exception as e:
                print(f"Error merging subsection {sub_idx}: {e}")
        
        if not merged_clips:
            return {"video_path": None, "audio_path": None}
        
        # Concatenate all merged clips into final section video
        final_video = output_dir / "final_section.mp4"
        final_audio = output_dir / "audio.mp3"  # Keep original name for compatibility
        
        # Create concat file
        concat_file = output_dir / "concat_list.txt"
        with open(concat_file, "w") as f:
            for clip in merged_clips:
                f.write(f"file '{clip}'\n")
        
        # Concatenate videos
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(final_video)
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
                print(f"FFmpeg concat error: {result.stderr}")
        except Exception as e:
            print(f"Error concatenating subsections: {e}")
            # Use first clip as fallback
            if merged_clips:
                import shutil
                shutil.copy(merged_clips[0], str(final_video))
        
        # Extract audio from final video for compatibility
        if final_video.exists():
            cmd = [
                "ffmpeg", "-y",
                "-i", str(final_video),
                "-vn",
                "-acodec", "libmp3lame",
                str(final_audio)
            ]
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    timeout=120
                )
            except Exception as e:
                print(f"Error extracting audio: {e}")
        
        return {
            "video_path": str(final_video) if final_video.exists() else None,
            "audio_path": str(final_audio) if final_audio.exists() else None
        }

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
        """Combine video sections with their audio
        
        IMPORTANT: Video is extended to match audio duration if shorter.
        We freeze the last frame of video to fill any gap.
        """
        
        # First, merge each video with its audio
        merged_sections = []
        
        for i, (video, audio) in enumerate(zip(videos, audios)):
            merged_path = Path(sections_dir) / f"merged_{i}.mp4"
            
            if audio is None:
                # No audio for this section - just copy the video
                print(f"Section {i}: No audio, using video as-is")
                merged_sections.append(video)
                continue
            
            # Get audio duration first
            audio_duration = await self._get_media_duration(audio)
            video_duration = await self._get_media_duration(video)
            
            print(f"Section {i}: Video={video_duration:.1f}s, Audio={audio_duration:.1f}s")
            
            if video_duration >= audio_duration:
                # Video is long enough, just merge with -shortest
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
            else:
                # Video is shorter than audio - extend video with tpad filter (freeze last frame)
                print(f"Section {i}: Extending video by {audio_duration - video_duration:.1f}s to match audio")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", video,
                    "-i", audio,
                    "-filter_complex", f"[0:v]tpad=stop=-1:stop_mode=clone,setpts=PTS-STARTPTS[v]",
                    "-map", "[v]",
                    "-map", "1:a:0",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-t", str(audio_duration),  # Cut to audio duration
                    str(merged_path)
                ]
            
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    print(f"FFmpeg error section {i}: {result.stderr}")
                
                if merged_path.exists():
                    merged_sections.append(str(merged_path))
                else:
                    print(f"Merged file not created for section {i}, using video")
                    merged_sections.append(video)
            except Exception as e:
                print(f"Error merging section {i}: {e}")
                # Use original video if merge fails
                merged_sections.append(video)
        
        # Now concatenate all merged sections
        if merged_sections:
            await self._concatenate_videos(merged_sections, output_path)
    
    async def _get_media_duration(self, file_path: str) -> float:
        """Get duration of a media file using ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Error getting duration for {file_path}: {e}")
            return 0.0
        
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
