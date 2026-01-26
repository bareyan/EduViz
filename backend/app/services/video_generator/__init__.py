"""
Video Generator - Orchestrates the complete video generation pipeline
Generates videos section-by-section with proper audio sync
"""

import os
import json
import asyncio
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from ..analyzer import MaterialAnalyzer
from ..script_generation import ScriptGenerator
from ..manim_generator import ManimGenerator
from ..tts_engine import TTSEngine

from .audio_video_utils import combine_sections, concatenate_videos
from .section_processor import (
    clean_narration_for_tts,
    process_single_subsection,
    process_segments_audio_first,
)


class VideoGenerator:
    """Orchestrates the complete video generation pipeline"""
    
    def __init__(self, output_base_dir: str):
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.analyzer = MaterialAnalyzer()
        self.script_generator = ScriptGenerator()
        self.manim_generator = ManimGenerator()
        self.tts_engine = TTSEngine()
    
    def check_existing_progress(self, job_id: str) -> Dict[str, Any]:
        """Check what progress already exists for a job"""
        job_dir = self.output_base_dir / job_id
        result = {
            "has_script": False,
            "script": None,
            "completed_sections": [],
            "has_final_video": False,
            "total_sections": 0
        }
        
        if not job_dir.exists():
            return result
        
        # Check for script
        script_path = job_dir / "script.json"
        if script_path.exists():
            try:
                with open(script_path, "r") as f:
                    result["script"] = json.load(f)
                    result["has_script"] = True
                    result["total_sections"] = len(result["script"].get("sections", []))
            except Exception as e:
                print(f"[Resume] Failed to load script.json: {e}")
        
        # Check for completed sections
        sections_dir = job_dir / "sections"
        if sections_dir.exists() and result["script"]:
            sections = result["script"].get("sections", [])
            for i, section in enumerate(sections):
                section_id = section.get("id", f"section_{i}")
                section_dir = sections_dir / section_id
                
                merged_path = sections_dir / f"merged_{i}.mp4"
                final_section_path = section_dir / "final_section.mp4"
                
                if merged_path.exists() or final_section_path.exists():
                    result["completed_sections"].append(i)
                    print(f"[Resume] Section {i} ({section_id}): Found completed video")
                else:
                    print(f"[Resume] Section {i} ({section_id}): No completed video found, will regenerate")
        
        # Check for final video
        final_video_path = job_dir / "final_video.mp4"
        result["has_final_video"] = final_video_path.exists()
        
        return result
    
    async def generate_video(
        self,
        file_path: str,
        file_id: str,
        topic: Dict[str, Any],
        voice: str = "en-US-GuyNeural",
        progress_callback: Optional[callable] = None,
        job_id: Optional[str] = None,
        video_mode: str = "comprehensive",
        style: str = "3b1b",
        language: str = "en",
        content_focus: str = "as_document",
        document_context: str = "auto",
        resume: bool = False
    ) -> Dict[str, Any]:
        """Generate a complete video for a topic"""
        
        # Debug logging
        print(f"[VideoGenerator] Starting video generation")
        print(f"[VideoGenerator] File path: {file_path}")
        print(f"[VideoGenerator] File exists: {os.path.exists(file_path)}")
        print(f"[VideoGenerator] Topic: {topic.get('title', 'Unknown')}")
        print(f"[VideoGenerator] Video mode: {video_mode}")
        print(f"[VideoGenerator] Language: {language}")
        print(f"[VideoGenerator] Content focus: {content_focus}")
        print(f"[VideoGenerator] Document context: {document_context}")
        
        # Create job directory
        if not job_id:
            job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_id}"
        job_dir = self.output_base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        sections_dir = job_dir / "sections"
        sections_dir.mkdir(exist_ok=True)
        
        # Set up visual QC error tracking
        if self.manim_generator.visual_qc:
            self.manim_generator.visual_qc.set_errors_dir(str(job_dir))
            self.manim_generator.visual_qc.clear_error_frames()
        
        # Check for existing progress
        existing_progress = None
        completed_section_indices = set()
        if resume and job_id:
            existing_progress = self.check_existing_progress(job_id)
            if existing_progress["has_final_video"]:
                print(f"[Resume] Final video already exists, returning completed status")
                script = existing_progress["script"]
                return {
                    "status": "completed",
                    "script": script,
                    "job_id": job_id,
                    "total_duration": sum(s.get("duration_seconds", 30) for s in script.get("sections", [])),
                    "chapters": []
                }
            if existing_progress["has_script"]:
                print(f"[Resume] Found existing script with {existing_progress['total_sections']} sections")
                print(f"[Resume] Completed sections: {len(existing_progress['completed_sections'])}/{existing_progress['total_sections']}")
                completed_section_indices = set(existing_progress["completed_sections"])
        
        try:
            # Step 1: Generate or load the script
            if resume and existing_progress and existing_progress["has_script"]:
                script = existing_progress["script"]
                print(f"[Resume] Using existing script: {script.get('title', 'Unknown')}")
                if progress_callback:
                    progress_callback({"stage": "script", "progress": 100, "message": f"Resuming with existing script ({len(script.get('sections', []))} sections)"})
            else:
                if progress_callback:
                    progress_callback({"stage": "script", "progress": 0, "message": f"Generating {video_mode} script..."})
                
                print(f"[VideoGenerator] Calling script generator with file: {file_path}")
                
                script = await self.script_generator.generate_script(
                    file_path=file_path,
                    topic=topic,
                    max_duration_minutes=topic.get("estimated_duration_minutes", 15),
                    video_mode=video_mode,
                    language=language,
                    content_focus=content_focus,
                    document_context=document_context
                )
                
                print(f"[VideoGenerator] Script generated with {len(script.get('sections', []))} sections")
                
                # Save script
                script_path = job_dir / "script.json"
                with open(script_path, "w") as f:
                    json.dump(script, f, indent=2)
            
            sections = script.get("sections", [])
            total_sections = len(sections)
            
            if progress_callback:
                progress_callback({"stage": "script", "progress": 100, "message": f"Script ready with {total_sections} sections"})
            # Step 2: Process sections
            section_videos = []
            section_audios = []
            chapters = []
            current_time = 0
            
            max_concurrent = min(8, os.cpu_count() or 2)
            semaphore = asyncio.Semaphore(max_concurrent)
            completed_count = [0]
            
            async def process_section(i: int, section: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single section"""
                async with semaphore:
                    section_id = section.get("id", f"section_{i}")
                    section_dir = sections_dir / section_id
                    section_dir.mkdir(exist_ok=True)
                    
                    result = {
                        "index": i,
                        "video_path": None,
                        "audio_path": None,
                        "duration": section.get("duration_seconds", 30),
                        "title": section.get("title", f"Section {i + 1}")
                    }
                    
                    # Check for existing completed section
                    merged_path = sections_dir / f"merged_{i}.mp4"
                    final_section_path = section_dir / "final_section.mp4"
                    
                    existing_video_path = None
                    if merged_path.exists():
                        existing_video_path = str(merged_path)
                    elif final_section_path.exists():
                        existing_video_path = str(final_section_path)
                    
                    if resume and i in completed_section_indices and existing_video_path:
                        print(f"[Resume] Skipping section {i + 1}/{total_sections} (already completed)")
                        result["video_path"] = existing_video_path
                        section_audio_path = section_dir / "section_audio.mp3"
                        if section_audio_path.exists():
                            result["audio_path"] = str(section_audio_path)
                        completed_count[0] += 1
                        if progress_callback:
                            progress_callback({
                                "stage": "sections",
                                "progress": int((completed_count[0] / total_sections) * 100),
                                "message": f"Resumed section {completed_count[0]}/{total_sections} (cached)"
                            })
                        return result
                    
                    print(f"[Parallel] Starting section {i + 1}/{total_sections}: {section.get('title', '')}")
                    
                    narration_segments = section.get("narration_segments", [])
                    
                    if not narration_segments:
                        tts_text = section.get("tts_narration") or section.get("narration", "")
                        clean_narration = clean_narration_for_tts(tts_text)
                        
                        subsection_results = await process_single_subsection(
                            generator=self,
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
                        segment_result = await process_segments_audio_first(
                            generator=self,
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
                    
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback({
                            "stage": "sections",
                            "progress": int((completed_count[0] / total_sections) * 100),
                            "message": f"Completed section {completed_count[0]}/{total_sections}"
                        })
                    
                    print(f"[Parallel] Finished section {i + 1}/{total_sections}")
                    return result
            
            if progress_callback:
                progress_callback({
                    "stage": "sections",
                    "progress": 0,
                    "message": f"Processing {total_sections} sections in parallel (max {max_concurrent} concurrent)..."
                })
            
            section_tasks = [process_section(i, section) for i, section in enumerate(sections)]
            section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(section_results):
                if isinstance(result, Exception):
                    print(f"Section {i} processing error: {result}")
                    continue
                
                if i < len(sections):
                    sections[i]["order"] = i
                
                video_path = result.get("video_path")
                audio_path = result.get("audio_path")
                
                if video_path and audio_path:
                    section_videos.append(video_path)
                    section_audios.append(audio_path)
                    if i < len(sections):
                        sections[i]["video"] = video_path
                        sections[i]["audio"] = audio_path
                elif video_path:
                    section_videos.append(video_path)
                    section_audios.append(None)
                    if i < len(sections):
                        sections[i]["video"] = video_path
                    print(f"Warning: Section {i} has video but no audio")
                elif audio_path:
                    if i < len(sections):
                        sections[i]["audio"] = audio_path
                    print(f"Warning: Section {i} has audio but no video - SKIPPING from final video")
                else:
                    print(f"Warning: Section {i} has neither video nor audio - SKIPPING")
                    continue
                
                if result.get("manim_code_path") and i < len(sections):
                    sections[i]["manim_code_path"] = result["manim_code_path"]
                    if "manim_code" in sections[i]:
                        del sections[i]["manim_code"]
                
                if video_path:
                    chapters.append({
                        "title": result["title"],
                        "start_time": current_time,
                        "duration": result["duration"]
                    })
                    current_time += result["duration"]
            
            if progress_callback:
                progress_callback({"stage": "sections", "progress": 100, "message": "All sections processed"})
            
            # Save updated script
            script_path = job_dir / "script.json"
            with open(script_path, "w") as f:
                json.dump(script, f, indent=2)
            print(f"Saved updated script.json with manim_code for {len(sections)} sections")
            
            # Step 3: Combine sections
            if progress_callback:
                progress_callback({"stage": "combining", "progress": 0, "message": "Combining sections..."})
            
            final_video_path = job_dir / "final_video.mp4"
            
            if section_videos and section_audios:
                await combine_sections(
                    videos=section_videos,
                    audios=section_audios,
                    output_path=str(final_video_path),
                    sections_dir=str(sections_dir)
                )
            elif section_videos:
                await concatenate_videos(section_videos, str(final_video_path))
            else:
                raise ValueError("No video sections were generated")
            
            if progress_callback:
                progress_callback({"stage": "combining", "progress": 100, "message": "Video complete!"})
            
            # Print summaries
            if self.manim_generator.visual_qc:
                self.manim_generator.visual_qc.print_error_summary()
            
            print("\n")
            self.manim_generator.print_generation_stats()
            self.manim_generator.print_cost_summary()
            
            cost_summary = self.manim_generator.get_cost_summary()
            
            # Cleanup
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
        """Remove intermediate files after successful generation"""
        try:
            for section_path in sections_dir.iterdir():
                if section_path.is_dir():
                    # Remove manim media folders
                    media_dir = section_path / "media"
                    if media_dir.exists():
                        shutil.rmtree(media_dir)
                    # Remove fallback files
                    for f in section_path.glob("fallback_*.py"):
                        f.unlink()
                    # Remove __pycache__
                    pycache_dir = section_path / "__pycache__"
                    if pycache_dir.exists():
                        shutil.rmtree(pycache_dir)
            print("Cleaned up intermediate files (preserved .py, .mp4, .mp3 files)")
        except Exception as e:
            print(f"Cleanup error (non-fatal): {e}")


# Re-export for backward compatibility
__all__ = ['VideoGenerator']
