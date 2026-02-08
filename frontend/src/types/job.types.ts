import { SectionProgress } from './section.types'
export type { SectionProgress }

export interface VideoChapter {
  title: string
  start_time: number
  duration: number
}

export interface GeneratedVideo {
  video_id: string
  title: string
  duration: number
  chapters: VideoChapter[]
  download_url: string
  thumbnail_url?: string
}

export interface JobResponse {
  job_id: string
  status: 'pending' | 'analyzing' | 'generating_script' | 'creating_animations' | 'synthesizing_audio' | 'composing_video' | 'completed' | 'failed'
  progress: number
  message: string
  result?: GeneratedVideo[]
}

export interface DetailedProgress {
  job_id: string
  status: string
  progress: number
  message: string
  current_stage: 'analyzing' | 'script' | 'sections' | 'combining' | 'completed' | 'failed' | 'unknown'
  current_section_index?: number
  script_ready: boolean
  script_title?: string
  total_sections: number
  completed_sections: number
  sections: SectionProgress[]
}

export interface GalleryJob {
  id: string
  status: string
  progress: number
  message: string
  created_at: string
  updated_at: string
  video_exists?: boolean
  video_url?: string
  title?: string
  total_duration?: number
  sections_count?: number
}

export interface SectionFile {
  id: string
  files: Record<string, string>
  video?: string
  audio?: string
}

export interface SectionEdit {
  id: string;
  title: string;
  narration: string;
  duration_seconds: number;
  visual_description: string;
  manim_code: string;
  video?: string;
  audio?: string;
}

export interface SectionDetails {
  index: number
  id: string
  title: string
  duration_seconds?: number
  narration: string
  visual_description: string
  narration_segments: Array<{
    segment_id: string
    visual_description: string
    narration: string
    duration_seconds: number
  }>
  code?: string
  video_url?: string
  has_audio: boolean
  has_video: boolean
}

export interface ResumeInfo {
  job_id: string
  has_script: boolean
  total_sections: number
  completed_sections: number
  has_final_video: boolean
  can_resume: boolean
}
