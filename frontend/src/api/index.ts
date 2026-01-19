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

export async function generateVideos(params: {
  file_id: string
  analysis_id: string
  selected_topics: number[]
  style?: string
  max_video_length?: number
  voice?: string
  video_mode?: 'comprehensive' | 'overview'
  language?: string
}): Promise<JobResponse> {
  const response = await api.post('/generate', params)
  return response.data
}

export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const response = await api.get(`/job/${jobId}`)
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

export default api
