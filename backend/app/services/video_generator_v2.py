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
        
        # Set up visual QC error tracking directory
        if self.manim_generator.visual_qc:
            self.manim_generator.visual_qc.set_errors_dir(str(job_dir))
            self.manim_generator.visual_qc.clear_error_frames()  # Clear from any previous runs
        
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
            
            # Step 2: Generate audio and video for each section
            # NEW WORKFLOW: Audio-first approach for precise sync
            # 1. Generate audio for all segments first
            # 2. Get actual audio durations
            # 3. Pass timing info to Gemini for video generation
            # 4. One video per segment, compiled together
            section_videos = []
            section_audios = []
            chapters = []
            current_time = 0
            
            # Limit concurrent processing to avoid overwhelming system
            max_concurrent = min(8, os.cpu_count() or 2)
            semaphore = asyncio.Semaphore(max_concurrent)
            
            # Track progress across parallel tasks
            completed_count = [0]
            
            # Process sections in parallel for faster generation
            async def process_section(i: int, section: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single section using audio-first segment approach
                
                NEW WORKFLOW:
                1. Get pre-defined narration segments from script (~10s each)
                2. Generate audio for ALL segments first
                3. Get actual audio durations
                4. Pass segment timing info to Gemini for video generation
                5. Generate one video per segment
                6. Merge segment videos+audios together
                """
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
                    
                    # Check if we have pre-segmented narration from script generator
                    narration_segments = section.get("narration_segments", [])
                    
                    if not narration_segments:
                        # Fallback: no segments, use old single-subsection flow
                        tts_text = section.get("tts_narration") or section.get("narration", "")
                        clean_narration = self._clean_narration_for_tts(tts_text)
                        
                        subsection_results = await self._process_single_subsection(
                            section=section,
                            narration=clean_narration,
                            section_dir=section_dir,
                            section_index=i,
                            voice=voice,
                            style=style,
                            language=language
                        )
                        result["video_path"] = subsection_results.get("video_path")
                        result["audio_path"] = subsection_results.get("audio_path")
                        result["duration"] = subsection_results.get("duration", 30)
                        if subsection_results.get("manim_code_path"):
                            section["manim_code_path"] = subsection_results["manim_code_path"]
                            result["manim_code_path"] = subsection_results["manim_code_path"]
                        if subsection_results.get("manim_code"):
                            result["manim_code"] = subsection_results["manim_code"]
                    else:
                        # NEW: Audio-first segment processing
                        segment_result = await self._process_segments_audio_first(
                            section=section,
                            narration_segments=narration_segments,
                            section_dir=section_dir,
                            section_index=i,
                            voice=voice,
                            style=style,
                            language=language
                        )
                        result["video_path"] = segment_result.get("video_path")
                        result["audio_path"] = segment_result.get("audio_path")
                        result["duration"] = segment_result.get("duration", 30)
                        if segment_result.get("manim_code_path"):
                            section["manim_code_path"] = segment_result["manim_code_path"]
                            result["manim_code_path"] = segment_result["manim_code_path"]
                        if segment_result.get("manim_code"):
                            result["manim_code"] = segment_result["manim_code"]
                    
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
                    
                # Store manim_code_path if present in result (prefer path over code content)
                if result.get("manim_code_path") and i < len(sections):
                    sections[i]["manim_code_path"] = result["manim_code_path"]
                    # Remove manim_code from section to avoid storing large code in script.json
                    if "manim_code" in sections[i]:
                        del sections[i]["manim_code"]
                
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
            
            # Step 4: Print Visual QC error summary (for debugging)
            if self.manim_generator.visual_qc:
                self.manim_generator.visual_qc.print_error_summary()
            
            # Step 5: Print cost summary
            print("\n")
            self.manim_generator.print_cost_summary()
            
            # Get cost data for return
            cost_summary = self.manim_generator.get_cost_summary()
            
            # Step 6: Cleanup intermediate files (but KEEP scene .py files)
            await self._cleanup_intermediate_files(sections_dir)
            
            return {
                "job_id": job_id,
                "video_path": str(final_video_path),
                "script": script,
                "chapters": chapters,
                "total_duration": current_time,
                "cost_summary": cost_summary,
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
        style: str,
        language: str = "en"
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
                style=style,
                language=language
            )
            video_path = manim_result.get("video_path") if isinstance(manim_result, dict) else manim_result
            if video_path and os.path.exists(video_path):
                result["video_path"] = video_path
            if isinstance(manim_result, dict):
                # Store path to manim code file, not the code itself
                if manim_result.get("manim_code_path"):
                    result["manim_code_path"] = manim_result["manim_code_path"]
                # Keep manim_code for backward compatibility (in-memory use only)
                if manim_result.get("manim_code"):
                    result["manim_code"] = manim_result["manim_code"]
        except Exception as e:
            print(f"Manim error for section {section_index}: {e}")
        
        return result
    
    async def _process_segments_audio_first(
        self,
        section: Dict[str, Any],
        narration_segments: List[Dict[str, Any]],
        section_dir: Path,
        section_index: int,
        voice: str,
        style: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Process segments using audio-first approach for precise sync
        
        WORKFLOW:
        1. Generate audio for ALL segments first
        2. Get actual audio durations for each segment
        3. Concatenate all audio into one section audio file
        4. Pass ALL segment timing info to Gemini for ONE cohesive video
        5. Generate ONE video for the entire section
        6. Merge audio with video
        
        This creates smooth, continuous animations within each section.
        """
        result = {
            "video_path": None,
            "audio_path": None,
            "duration": 0,
            "manim_code": None
        }
        
        num_segments = len(narration_segments)
        print(f"Section {section_index}: Processing {num_segments} segments (audio-first, unified video)")
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 1: Generate audio for ALL segments first
        # ═══════════════════════════════════════════════════════════════════════
        segment_audio_info = []
        cumulative_time = 0.0
        
        for seg_idx, segment in enumerate(narration_segments):
            seg_dir = section_dir / f"seg_{seg_idx}"
            seg_dir.mkdir(exist_ok=True)
            
            seg_text = segment.get("text", "")
            clean_text = self._clean_narration_for_tts(seg_text)
            
            audio_path = seg_dir / "audio.mp3"
            audio_duration = segment.get("estimated_duration", 10.0)
            
            try:
                await self.tts_engine.generate_speech(
                    text=clean_text,
                    output_path=str(audio_path),
                    voice=voice
                )
                audio_duration = await self._get_audio_duration(str(audio_path))
            except Exception as e:
                print(f"TTS error for section {section_index} segment {seg_idx}: {e}")
                audio_path = None
            
            # Build timing info
            segment_info = {
                "segment_index": seg_idx,
                "text": clean_text,
                "audio_path": str(audio_path) if audio_path else None,
                "duration": audio_duration,
                "start_time": cumulative_time,
                "end_time": cumulative_time + audio_duration,
                "seg_dir": str(seg_dir)
            }
            segment_audio_info.append(segment_info)
            cumulative_time += audio_duration
            
            print(f"  Segment {seg_idx}: {audio_duration:.1f}s (starts at {segment_info['start_time']:.1f}s)")
        
        total_duration = cumulative_time
        print(f"Section {section_index}: Total audio duration = {total_duration:.1f}s")
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 2: Concatenate all audio segments into one file
        # ═══════════════════════════════════════════════════════════════════════
        section_audio_path = section_dir / "section_audio.mp3"
        valid_audio_paths = [s["audio_path"] for s in segment_audio_info if s["audio_path"]]
        
        if len(valid_audio_paths) > 1:
            await self._concatenate_audio_files(valid_audio_paths, str(section_audio_path))
        elif len(valid_audio_paths) == 1:
            import shutil
            shutil.copy(valid_audio_paths[0], str(section_audio_path))
        else:
            print(f"Section {section_index}: No valid audio segments")
            return result
        
        result["audio_path"] = str(section_audio_path)
        result["duration"] = total_duration
        
        # Build unified section data with ALL segment timing information
        # The Manim generator will create ONE continuous animation that covers all segments
        unified_section = {
            "id": section.get('id', 'section'),
            "title": section.get('title', 'Section'),
            # Combine all segment narrations into one
            "narration": "\n\n".join([s["text"] for s in segment_audio_info]),
            "tts_narration": "\n\n".join([s["text"] for s in segment_audio_info]),
            "visual_description": section.get("visual_description", ""),
            "key_concepts": section.get("key_concepts", []),
            "animation_type": section.get("animation_type", "mixed"),
            "style": style,
            "language": language,
            # CRITICAL: Timing information for the ENTIRE section
            "total_duration": total_duration,
            "is_unified_section": True,
            "num_segments": num_segments,
            # Detailed timing breakdown for each narration segment
            # This helps Gemini time animations to sync with each part of the narration
            "segment_timing": [
                {
                    "index": s["segment_index"],
                    "text": s["text"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "duration": s["duration"]
                }
                for s in segment_audio_info
            ]
        }
        
        print(f"Section {section_index}: Generating unified video ({total_duration:.1f}s total)")
        
        video_path = None
        manim_code = None
        
        try:
            manim_result = await self.manim_generator.generate_section_video(
                section=unified_section,
                output_dir=str(section_dir),
                section_index=str(section_index),
                audio_duration=total_duration,
                style=style,
                language=language
            )
            video_path = manim_result.get("video_path") if isinstance(manim_result, dict) else manim_result
            if isinstance(manim_result, dict) and manim_result.get("manim_code"):
                manim_code = manim_result["manim_code"]
        except Exception as e:
            print(f"Manim error for unified section {section_index}: {e}")
            import traceback
            traceback.print_exc()
            return result
        
        if not video_path:
            print(f"Section {section_index}: Failed to generate unified video")
            return result
        
        result["manim_code"] = manim_code
        
        # ═══════════════════════════════════════════════════════════════════════
        # STEP 4: Merge unified video with concatenated audio
        # ═══════════════════════════════════════════════════════════════════════
        merged_path = section_dir / "final_section.mp4"
        
        audio_duration_actual = await self._get_media_duration(str(section_audio_path))
        video_duration_actual = await self._get_media_duration(video_path)
        
        print(f"Section {section_index}: Merging video ({video_duration_actual:.1f}s) with audio ({audio_duration_actual:.1f}s)")
        
        # Never trim: retime video to match audio duration
        cmd = self._build_retime_merge_cmd(
            video_path=video_path,
            audio_path=str(section_audio_path),
            video_duration=video_duration_actual,
            audio_duration=audio_duration_actual,
            output_path=str(merged_path)
        )
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            
            if process.returncode == 0 and merged_path.exists():
                result["video_path"] = str(merged_path)
                result["duration"] = total_duration
                print(f"Section {section_index}: Successfully created unified video")
            else:
                print(f"Section {section_index}: FFmpeg merge failed: {stderr.decode()[:500]}")
        except Exception as e:
            print(f"Section {section_index}: Error merging video and audio: {e}")
        
        return result
    
    async def _merge_single_segment(
        self,
        segment: Dict[str, Any],
        output_dir: Path,
        section_index: int
    ) -> Dict[str, Any]:
        """Merge a single segment's video and audio"""
        video_path = segment["video_path"]
        audio_path = segment["audio_path"]
        
        merged_path = output_dir / "final_section.mp4"
        final_audio = output_dir / "audio.mp3"
        
        # Get durations
        audio_duration = await self._get_media_duration(audio_path)
        video_duration = await self._get_media_duration(video_path)
        
        cmd = self._build_retime_merge_cmd(
            video_path=video_path,
            audio_path=audio_path,
            video_duration=video_duration,
            audio_duration=audio_duration,
            output_path=str(merged_path)
        )
        
        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
        except Exception as e:
            print(f"Error merging segment: {e}")
            return {"video_path": None, "audio_path": None}
        
        # Copy audio for compatibility
        if os.path.exists(audio_path):
            import shutil
            shutil.copy(audio_path, str(final_audio))
        
        return {
            "video_path": str(merged_path) if merged_path.exists() else None,
            "audio_path": str(final_audio) if final_audio.exists() else None
        }
    
    async def _concatenate_audio_files(
        self,
        audio_paths: List[str],
        output_path: str
    ) -> bool:
        """Concatenate multiple audio files into one using ffmpeg"""
        if not audio_paths:
            return False
        
        if len(audio_paths) == 1:
            import shutil
            shutil.copy(audio_paths[0], output_path)
            return True
        
        # Create concat file list
        concat_list_path = Path(output_path).parent / "concat_audio_list.txt"
        with open(concat_list_path, 'w') as f:
            for audio_path in audio_paths:
                f.write(f"file '{audio_path}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            output_path
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            
            if process.returncode != 0:
                print(f"Audio concatenation failed: {stderr.decode()[:500]}")
                return False
            
            return Path(output_path).exists()
        except Exception as e:
            print(f"Error concatenating audio: {e}")
            return False
        finally:
            # Cleanup
            if concat_list_path.exists():
                concat_list_path.unlink()
    
    async def _merge_segments(
        self,
        segment_results: List[Dict[str, Any]],
        output_dir: Path,
        section_index: int
    ) -> Dict[str, Any]:
        """Merge multiple segments into a single section video
        1. Merge each segment's audio+video
        2. Concatenate all merged clips
        """
        merged_clips = []
        
        for seg in segment_results:
            seg_idx = seg["segment_index"]
            video_path = seg.get("video_path")
            audio_path = seg.get("audio_path")
            merged_path = output_dir / f"merged_seg_{seg_idx}.mp4"
            
            audio_duration = await self._get_media_duration(audio_path)
            video_duration = await self._get_media_duration(video_path)
            
            cmd = self._build_retime_merge_cmd(
                video_path=video_path,
                audio_path=audio_path,
                video_duration=video_duration,
                audio_duration=audio_duration,
                output_path=str(merged_path)
            )
            
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
            except Exception as e:
                print(f"Error merging segment {seg_idx}: {e}")
        
        if not merged_clips:
            return {"video_path": None, "audio_path": None}
        
        # Concatenate all merged clips
        final_video = output_dir / "final_section.mp4"
        final_audio = output_dir / "audio.mp3"
        
        concat_file = output_dir / "concat_list.txt"
        with open(concat_file, "w") as f:
            for clip in merged_clips:
                f.write(f"file '{clip}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(final_video)
        ]
        
        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
        except Exception as e:
            print(f"Error concatenating segments: {e}")
            if merged_clips:
                import shutil
                shutil.copy(merged_clips[0], str(final_video))
        
        # Extract audio
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
            except Exception:
                pass
        
        return {
            "video_path": str(final_video) if final_video.exists() else None,
            "audio_path": str(final_audio) if final_audio.exists() else None
        }
    
    async def _process_subsections_with_sync(
        self,
        section: Dict[str, Any],
        subsections: List[Dict[str, Any]],
        section_dir: Path,
        section_index: int,
        voice: str,
        style: str,
        language: str = "en"
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
                "language": language,
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
                    style=style,
                    language=language
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
            
            cmd = self._build_retime_merge_cmd(
                video_path=video_path,
                audio_path=audio_path,
                video_duration=video_duration,
                audio_duration=audio_duration,
                output_path=str(merged_path)
            )
            
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

    async def _pad_audio_with_silence(
        self,
        audio_path: str,
        target_duration: float,
        output_path: str
    ) -> str:
        """Pad audio with silence to reach target duration (no trimming)."""
        try:
            current_duration = await self._get_media_duration(audio_path)
        except Exception:
            current_duration = 0.0

        if current_duration >= target_duration - 0.05:
            return audio_path

        silence_duration = max(0.0, target_duration - current_duration)
        silence_path = str(Path(output_path).with_suffix(".silence.mp3"))

        try:
            await self._generate_silence(silence_path, silence_duration)
            success = await self._concatenate_audio_files(
                [audio_path, silence_path],
                output_path
            )
            if success and Path(output_path).exists():
                return output_path
        finally:
            if Path(silence_path).exists():
                Path(silence_path).unlink()

        return audio_path

    def _build_retime_merge_cmd(
        self,
        video_path: str,
        audio_path: str,
        video_duration: float,
        audio_duration: float,
        output_path: str
    ) -> List[str]:
        """Build ffmpeg command to retime video to audio length without trimming."""
        if not video_duration or not audio_duration:
            return [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-c:a", "aac",
                output_path
            ]

        duration_diff = abs(video_duration - audio_duration)
        if duration_diff < 0.1:
            return [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-c:a", "aac",
                output_path
            ]

        speed_factor = audio_duration / video_duration
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", f"[0:v]setpts=PTS*{speed_factor}[v]",
            "-map", "[v]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]
    
    async def _combine_sections(
        self,
        videos: List[str],
        audios: List[str],  # May contain None for sections without audio
        output_path: str,
        sections_dir: str
    ):
        """Combine video sections with their audio
    
    IMPORTANT: Never trim video. Retiming is used to match audio length.
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
            
            # CRITICAL: Never trim video. Retiming is used to match audio length.
            cmd = self._build_retime_merge_cmd(
                video_path=video,
                audio_path=audio,
                video_duration=video_duration,
                audio_duration=audio_duration,
                output_path=str(merged_path)
            )
            
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
