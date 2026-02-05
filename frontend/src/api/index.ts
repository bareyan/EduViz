import axios from 'axios'

export const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface UploadResponse {
  file_id: string
  filename: string
  size: number
  type: string
}

export interface TopicSuggestion {
  index: number
  title: string
  description: string
  estimated_duration: number
  complexity: 'beginner' | 'intermediate' | 'advanced'
  subtopics: string[]
}

export interface AnalysisResult {
  analysis_id: string
  file_id: string
  material_type: string
  total_content_pages: number
  detected_math_elements: number
  suggested_topics: TopicSuggestion[]
  estimated_total_videos: number
  summary: string
}

export interface VideoChapter {
  title: string
  start_time: number
  duration: number  // Changed from end_time to match backend
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

export interface Voice {
  id: string
  name: string
  gender: string
}

export interface Language {
  code: string
  name: string
}

export interface VoicesResponse {
  voices: Voice[]
  languages: Language[]
  current_language: string
  default_voice: string
}

// === Detailed Progress Types ===

export interface SectionProgress {
  index: number
  id: string
  title: string
  status: 'waiting' | 'generating_script' | 'generating_manim' | 'fixing_manim' | 'generating_audio' | 'generating_video' | 'fixing_error' | 'completed' | 'failed'
  duration_seconds?: number
  narration_preview?: string
  has_video: boolean
  has_audio: boolean
  has_code: boolean
  error?: string
  fix_attempts: number
  qc_iterations: number
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

// === Pipeline Types ===

export interface PipelineInfo {
  name: string
  description: string
  is_active: boolean
  models: {
    script_generation: string
    manim_generation: string
    visual_script_generation: string
  }
}

export interface PipelinesResponse {
  pipelines: PipelineInfo[]
  active: string
}

// API Functions
export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export async function analyzeFile(fileId: string): Promise<AnalysisResult> {
  const response = await api.post('/analyze', { file_id: fileId })
  return response.data
}

export async function getPipelines(): Promise<PipelinesResponse> {
  const response = await api.get('/pipelines')
  return response.data
}

export async function generateVideos(params: {
  file_id: string
  analysis_id: string
  selected_topics: number[]
  style?: string
  max_video_length?: number
  voice?: string
  video_mode?: 'comprehensive' | 'overview'
  language?: string
  content_focus?: 'practice' | 'theory' | 'as_document'
  document_context?: 'standalone' | 'series' | 'auto'
  pipeline?: string  // Pipeline configuration: "default", "high_quality", "cost_optimized"
  resume_job_id?: string  // If provided, resume this job instead of creating a new one
}): Promise<JobResponse> {
  const response = await api.post('/generate', params)
  return response.data
}

export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const response = await api.get(`/job/${jobId}`)
  return response.data
}

export async function getJobDetails(jobId: string): Promise<DetailedProgress> {
  const response = await api.get(`/job/${jobId}/details`)
  return response.data
}

// Resume info for a job
export interface ResumeInfo {
  job_id: string
  has_script: boolean
  total_sections: number
  completed_sections: number
  has_final_video: boolean
  can_resume: boolean
}

export async function getResumeInfo(jobId: string): Promise<ResumeInfo> {
  const response = await api.get(`/job/${jobId}/resume-info`)
  return response.data
}

export async function getVoices(language: string = 'en'): Promise<VoicesResponse> {
  const response = await api.get(`/voices?language=${language}`)
  return response.data
}

export async function deleteFile(fileId: string): Promise<void> {
  await api.delete(`/file/${fileId}`)
}

export function getVideoUrl(videoId: string): string {
  // Video files are stored at /outputs/{job_id}/final_video.mp4
  return `${API_BASE}/outputs/${videoId}/final_video.mp4`
}

// ============= Gallery & Job Management =============

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

// Full section details (for modal)
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

export async function getSectionDetails(jobId: string, sectionIndex: number): Promise<SectionDetails> {
  const response = await api.get(`/job/${jobId}/section/${sectionIndex}`)
  return response.data
}

export async function listAllJobs(): Promise<GalleryJob[]> {
  const response = await api.get('/jobs')
  return response.data.jobs
}

export async function listCompletedJobs(): Promise<GalleryJob[]> {
  const response = await api.get('/jobs/completed')
  return response.data.jobs
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`/job/${jobId}`)
}

export async function deleteFailedJobs(): Promise<{ deleted_count: number }> {
  const response = await api.delete('/jobs/failed')
  return response.data
}

export async function getJobScript(jobId: string): Promise<any> {
  const response = await api.get(`/job/${jobId}/script`)
  return response.data
}

export async function getJobSections(jobId: string): Promise<SectionFile[]> {
  const response = await api.get(`/job/${jobId}/sections`)
  return response.data.sections
}

export async function updateSectionCode(jobId: string, sectionId: string, filename: string, code: string): Promise<void> {
  await api.put(`/job/${jobId}/section/${sectionId}/code`, { filename, code })
}

export async function recompileJob(jobId: string): Promise<void> {
  await api.post(`/job/${jobId}/recompile`)
}

// ============= Translation =============

export interface Translation {
  language: string
  has_script: boolean
  has_video: boolean
  video_url: string | null
}

export interface TranslationsResponse {
  job_id: string
  original_language: string
  translations: Translation[]
}

export interface TranslationResponse {
  job_id: string
  translation_id: string
  target_language: string
  status: string
  message: string
}

export async function getJobTranslations(jobId: string): Promise<TranslationsResponse> {
  const response = await api.get(`/job/${jobId}/translations`)
  return response.data
}

export async function createTranslation(jobId: string, targetLanguage: string, voice?: string): Promise<TranslationResponse> {
  const response = await api.post(`/job/${jobId}/translate`, { 
    target_language: targetLanguage,
    voice: voice 
  })
  return response.data
}

// Available languages for translation
export const AVAILABLE_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'fr', name: 'French' },
  { code: 'es', name: 'Spanish' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'ar', name: 'Arabic' },
  { code: 'ru', name: 'Russian' },
  { code: 'ua', name: 'Ukrainian' },
  { code: 'hy', name: 'Armenian' },
  { code: 'hi', name: 'Hindi' },
  { code: 'tr', name: 'Turkish' },
  { code: 'pl', name: 'Polish' },
  { code: 'nl', name: 'Dutch' },
]

// Multilingual voices for translation (simplified)
export const MULTILINGUAL_VOICES = [
  { id: 'en-US-EmmaMultilingualNeural', name: 'Emma (Multilingual)', gender: 'female' },
  { id: 'fr-FR-VivienneMultilingualNeural', name: 'Vivienne (Multilingual)', gender: 'female' },
  { id: 'en-US-BrianMultilingualNeural', name: 'Brian (Multilingual)', gender: 'male' },
]

export default api
