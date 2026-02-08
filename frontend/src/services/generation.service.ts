import api, { API_BASE } from '../config/api.config'
import { JobResponse } from '../types/job.types'
import { PipelinesResponse } from '../types/pipeline.types'

export const generationService = {
  getPipelines: async (): Promise<PipelinesResponse> => {
    const response = await api.get('/pipelines')
    return response.data
  },

  generateVideos: async (params: {
    file_id: string
    analysis_id: string
    selected_topics: number[]
    style?: string
    voice?: string
    video_mode?: 'comprehensive' | 'overview'
    language?: string
    content_focus?: 'practice' | 'theory' | 'as_document'
    document_context?: 'standalone' | 'series' | 'auto'
    pipeline?: string
    resume_job_id?: string
  }): Promise<JobResponse> => {
    const response = await api.post('/generate', params)
    return response.data
  },

  getVideoUrl: (videoId: string): string => {
    return `${API_BASE}/outputs/${videoId}/final_video.mp4`
  }
}
