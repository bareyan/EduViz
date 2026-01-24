"""
Section management and editing routes
"""

import os
import re
import json
import subprocess
import shutil
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel

from ..config import OUTPUT_DIR
from ..services.job_manager import JobManager, JobStatus, get_job_manager

router = APIRouter(tags=["sections"])


class CodeUpdateRequest(BaseModel):
    code: str = ""
    manim_code: str = ""


class FixCodeRequest(BaseModel):
    prompt: str = ""
    frames: List[str] = []  # Base64 encoded images
    current_code: str = ""


@router.get("/job/{job_id}/sections")
async def get_job_sections(job_id: str):
    """Get all section files for a job (for editing)"""
    job_dir = OUTPUT_DIR / job_id
    sections_dir = job_dir / "sections"
    
    if not sections_dir.exists():
        raise HTTPException(status_code=404, detail="Sections not found")
    
    # Load script.json for metadata and ordering
    script_sections = []
    script_path = job_dir / "script.json"
    if script_path.exists():
        with open(script_path, "r") as f:
            script = json.load(f)
            script_sections = script.get("sections", [])
            script_sections = sorted(script_sections, key=lambda s: s.get("order", float('inf')))
    
    existing_folders = {f for f in os.listdir(sections_dir) if (sections_dir / f).is_dir()}
    
    sections = []
    processed_ids = set()
    
    for script_section in script_sections:
        section_id = script_section.get("id")
        if section_id and section_id in existing_folders:
            section_path = sections_dir / section_id
            section_info = script_section.copy()
            section_info["files"] = {}
            
            for f in os.listdir(section_path):
                full_path = section_path / f
                if f.endswith(".py"):
                    section_info["files"][f] = str(full_path)
                    if not section_info.get("manim_code"):
                        with open(full_path, "r") as pf:
                            section_info["manim_code"] = pf.read()
                elif f.endswith(".mp4"):
                    section_info["video"] = str(full_path)
                elif f.endswith(".mp3"):
                    section_info["audio"] = str(full_path)
            
            sections.append(section_info)
            processed_ids.add(section_id)
    
    for section_folder in sorted(existing_folders - processed_ids):
        section_path = sections_dir / section_folder
        section_info = {"id": section_folder, "files": {}}
        
        for f in os.listdir(section_path):
            full_path = section_path / f
            if f.endswith(".py"):
                section_info["files"][f] = str(full_path)
                if not section_info.get("manim_code"):
                    with open(full_path, "r") as pf:
                        section_info["manim_code"] = pf.read()
            elif f.endswith(".mp4"):
                section_info["video"] = str(full_path)
            elif f.endswith(".mp3"):
                section_info["audio"] = str(full_path)
        
        sections.append(section_info)
    
    return {"sections": sections}


@router.put("/job/{job_id}/section/{section_id}/code")
async def update_section_code(job_id: str, section_id: str, request: CodeUpdateRequest):
    """Update the Manim code for a section"""
    sections_dir = OUTPUT_DIR / job_id / "sections" / section_id
    
    if not sections_dir.exists():
        raise HTTPException(status_code=404, detail="Section not found")
    
    code = request.manim_code or request.code
    
    scene_file = None
    for f in os.listdir(sections_dir):
        if f.endswith(".py") and f.startswith("scene"):
            scene_file = f
            break
    
    filename = scene_file or "scene_0.py"
    code_path = sections_dir / filename
    with open(code_path, "w") as f:
        f.write(code)
    
    # Update script.json
    script_path = OUTPUT_DIR / job_id / "script.json"
    if script_path.exists():
        with open(script_path, "r") as f:
            script = json.load(f)
        
        for section in script.get("sections", []):
            if section.get("id") == section_id:
                section["manim_code"] = code
                break
        
        with open(script_path, "w") as f:
            json.dump(script, f, indent=2)
    
    return {"message": "Code updated successfully"}


@router.get("/file-content")
async def get_file_content(path: str):
    """Get the content of a file by path"""
    
    abs_path = os.path.abspath(path)
    abs_output_dir = os.path.abspath(str(OUTPUT_DIR))
    
    if not abs_path.startswith(abs_output_dir):
        raise HTTPException(status_code=403, detail="Access denied - path outside outputs directory")
    
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    ext = os.path.splitext(abs_path)[1].lower()
    
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }
    
    if ext in [".mp4", ".webm", ".mov", ".avi"]:
        return FileResponse(abs_path, media_type="video/mp4", headers=headers)
    elif ext in [".mp3", ".wav", ".ogg"]:
        return FileResponse(abs_path, media_type="audio/mpeg", headers=headers)
    elif ext in [".png", ".jpg", ".jpeg", ".gif"]:
        media_type = "image/png" if ext == ".png" else "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/gif"
        return FileResponse(abs_path, media_type=media_type, headers=headers)
    else:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return PlainTextResponse(content, headers=headers)


@router.post("/job/{job_id}/recompile")
async def recompile_job(job_id: str, background_tasks: BackgroundTasks):
    """Recompile a job's video from existing section files"""
    
    job_dir = OUTPUT_DIR / job_id
    sections_dir = job_dir / "sections"
    
    if not sections_dir.exists():
        raise HTTPException(status_code=404, detail="Job sections not found")
    
    async def run_recompile():
        try:
            get_job_manager().update_job(job_id, JobStatus.COMPOSING_VIDEO, 50, "Recompiling video...")
            
            script_path = job_dir / "script.json"
            ordered_sections = []
            if script_path.exists():
                try:
                    with open(script_path, "r") as sf:
                        script = json.load(sf)
                        ordered_sections = sorted(
                            script.get("sections", []),
                            key=lambda s: s.get("order", 0)
                        )
                except Exception as e:
                    print(f"Error reading script.json: {e}")

            if not ordered_sections:
                for section_folder in sorted(os.listdir(sections_dir)):
                    section_path = sections_dir / section_folder
                    if section_path.is_dir():
                        ordered_sections.append({"id": section_folder})

            if not ordered_sections:
                get_job_manager().update_job(job_id, JobStatus.FAILED, 0, "No sections found to recompile")
                return

            concat_file = job_dir / "concat_list.txt"
            combined_files = []

            for i, sec in enumerate(ordered_sections):
                section_id = sec.get("id")
                section_path = sections_dir / section_id
                
                video_file = sec.get("video")
                audio_file = sec.get("audio")
                
                if video_file and not os.path.exists(video_file):
                    video_file = None
                if audio_file and not os.path.exists(audio_file):
                    audio_file = None
                
                if not video_file and section_path.is_dir():
                    for root, dirs, files in os.walk(section_path):
                        for f in files:
                            if f.endswith(".mp4"):
                                video_file = os.path.join(root, f)
                                break
                        if video_file:
                            break
                
                if not audio_file and section_path.is_dir():
                    for f in os.listdir(section_path):
                        if f.endswith(".mp3"):
                            audio_file = str(section_path / f)
                            break

                if not video_file:
                    print(f"Skipping section {section_id}: no video found")
                    continue

                combined = job_dir / f"combined_{i:03d}.mp4"

                if audio_file:
                    def get_duration(file_path):
                        try:
                            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                                        "-of", "default=noprint_wrappers=1:nokey=1", file_path]
                            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                            return float(result.stdout.strip())
                        except:
                            return 0.0
                    
                    video_duration = get_duration(video_file)
                    audio_duration = get_duration(audio_file)
                    
                    if video_duration >= audio_duration:
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", video_file,
                            "-i", audio_file,
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-shortest",
                            str(combined)
                        ]
                    else:
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", video_file,
                            "-i", audio_file,
                            "-filter_complex", "[0:v]tpad=stop=-1:stop_mode=clone,setpts=PTS-STARTPTS[v]",
                            "-map", "[v]",
                            "-map", "1:a:0",
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-t", str(audio_duration),
                            str(combined)
                        ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", video_file,
                        "-c", "copy",
                        str(combined)
                    ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"ffmpeg error for section {section_id}: {result.stderr}")
                
                if combined.exists():
                    combined_files.append(str(combined))

            if not combined_files:
                get_job_manager().update_job(job_id, JobStatus.FAILED, 0, "No combined section videos produced")
                return

            with open(concat_file, "w") as f:
                for p in combined_files:
                    f.write(f"file '{p}'\n")

            final_video = job_dir / "final_video.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(final_video)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if final_video.exists():
                get_job_manager().update_job(job_id, JobStatus.COMPLETED, 100, "Video recompiled successfully!")
            else:
                get_job_manager().update_job(job_id, JobStatus.FAILED, 0, "Failed to create final video")
                
        except Exception as e:
            get_job_manager().update_job(job_id, JobStatus.FAILED, 0, f"Recompile error: {str(e)}")
    
    background_tasks.add_task(run_recompile)
    
    return {"message": "Recompile started", "job_id": job_id}


@router.post("/job/{job_id}/section/{section_id}/fix")
async def fix_section_code(job_id: str, section_id: str, request: FixCodeRequest):
    """Use LLM to fix/improve Manim code based on prompt and optional frame context"""
    import base64
    from ..services.llm import (
        LLMConfig, 
        ProviderType,
        get_llm_provider,
        get_default_provider_type
    )
    from ..config.models import get_model_for_provider
    
    sections_dir = OUTPUT_DIR / job_id / "sections" / section_id
    if not sections_dir.exists():
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Load section metadata
    script_path = OUTPUT_DIR / job_id / "script.json"
    section_info = {}
    if script_path.exists():
        with open(script_path, "r") as f:
            script = json.load(f)
            for section in script.get("sections", []):
                if section.get("id") == section_id:
                    section_info = section
                    break
    
    # Initialize LLM provider
    provider_type = get_default_provider_type()
    llm = get_llm_provider(provider_type)
    model = get_model_for_provider("manim_generation", provider_type)
    
    system_prompt = """You are an expert Manim animator, skilled at creating beautiful 3Blue1Brown-style mathematical animations.
Your task is to fix or improve the provided Manim code based on the user's request.

RULES:
1. Return ONLY the complete fixed Python code, no explanations
2. Keep the same class name and structure
3. Ensure the code is valid Manim CE (Community Edition) code
4. Make animations smooth and visually appealing
5. Use proper positioning, colors, and timing

Return ONLY the Python code, nothing else."""

    user_prompt = f"""Section Title: {section_info.get('title', 'Unknown')}
Section Description: {section_info.get('visual_description', 'N/A')}
Narration: {section_info.get('narration', 'N/A')}

CURRENT MANIM CODE:
```python
{request.current_code}
```

USER REQUEST: {request.prompt if request.prompt else 'Please review and fix any issues with this code.'}

Please provide the fixed/improved Manim code."""

    config = LLMConfig(
        model=model,
        temperature=0.3,
        max_tokens=8000,
        system_prompt=system_prompt,
        timeout=120.0
    )
    
    try:
        # Extract image bytes if provided
        image_data_list = []
        for i, frame_data in enumerate(request.frames[:5]):
            try:
                if "base64," in frame_data:
                    base64_data = frame_data.split("base64,")[1]
                    image_bytes = base64.b64decode(base64_data)
                    image_data_list.append((image_bytes, "image/png"))
            except Exception as e:
                print(f"Error processing frame {i}: {e}")
        
        # Use multimodal if images are provided and provider supports it
        if image_data_list and provider_type == ProviderType.GEMINI:
            response = await llm.generate_with_images(user_prompt, image_data_list, config)
        else:
            # For Ollama or when no images, use text-only
            if image_data_list:
                user_prompt = f"[Note: {len(image_data_list)} frame(s) were provided but image analysis is only available with Gemini provider]\n\n{user_prompt}"
            response = await llm.generate(user_prompt, config)
        
        fixed_code = response.text
        
        if "```python" in fixed_code:
            fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
        elif "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
        
        return {"fixed_code": fixed_code}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


@router.post("/job/{job_id}/section/{section_id}/regenerate")
async def regenerate_section(job_id: str, section_id: str):
    """Regenerate the video for a single section using its current Manim code"""
    
    sections_dir = OUTPUT_DIR / job_id / "sections" / section_id
    if not sections_dir.exists():
        raise HTTPException(status_code=404, detail="Section not found")
    
    try:
        code_file = None
        section_index = 0
        for f in os.listdir(sections_dir):
            if f.endswith(".py") and f.startswith("scene"):
                code_file = sections_dir / f
                idx_match = re.search(r"scene_(\d+)\.py", f)
                if idx_match:
                    section_index = int(idx_match.group(1))
                break
        
        if not code_file:
            raise HTTPException(status_code=404, detail="No Manim code file found in section")
        
        with open(code_file, "r") as f:
            code = f.read()
        
        class_match = re.search(r"class\s+(\w+)\s*\(", code)
        if not class_match:
            raise HTTPException(status_code=400, detail="Could not find Scene class in code")
        
        class_name = class_match.group(1)
        
        existing_video = None
        for f in os.listdir(sections_dir):
            if f.endswith(".mp4"):
                existing_video = f
                break
        
        output_video_name = existing_video or f"section_{section_index}.mp4"
        output_video = sections_dir / output_video_name
        
        if output_video.exists():
            output_video.unlink()
        
        for subdir in ["videos", "media", "images", "Tex", "texts"]:
            subdir_path = sections_dir / subdir
            if subdir_path.exists():
                shutil.rmtree(subdir_path)
        
        output_name = output_video_name.replace(".mp4", "")
        cmd = [
            "manim",
            "-ql",
            "--media_dir", str(sections_dir),
            "-o", output_name,
            str(code_file),
            class_name
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=str(sections_dir),
            timeout=120
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Manim render failed: {result.stderr[:500]}")
        
        video_found = False
        media_videos_dir = sections_dir / "videos"
        if media_videos_dir.exists():
            for root, dirs, files in os.walk(media_videos_dir):
                for f in files:
                    if f.endswith(".mp4"):
                        src = os.path.join(root, f)
                        shutil.move(src, str(output_video))
                        video_found = True
                        break
                if video_found:
                    break
            shutil.rmtree(media_videos_dir)
        
        if not video_found and not output_video.exists():
            raise HTTPException(status_code=500, detail="Manim did not produce a video file")
        
        script_path = OUTPUT_DIR / job_id / "script.json"
        if script_path.exists():
            with open(script_path, "r") as f:
                script = json.load(f)
            
            for section in script.get("sections", []):
                if section.get("id") == section_id:
                    section["video"] = str(output_video)
                    break
            
            with open(script_path, "w") as f:
                json.dump(script, f, indent=2)
        
        return {
            "message": "Section regenerated successfully",
            "section_id": section_id,
            "video_path": str(output_video)
        }
                
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Manim render timed out after 2 minutes")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")
