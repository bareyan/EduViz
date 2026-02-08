import api from '../config/api.config'
import { JobResponse, DetailedProgress, ResumeInfo, GalleryJob, SectionDetails, SectionEdit } from '../types/job.types'

export const jobService = {
  getJobStatus: async (jobId: string): Promise<JobResponse> => {
    const response = await api.get(`/job/${jobId}`)
    return response.data
  },

  getJobDetails: async (jobId: string): Promise<DetailedProgress> => {
    const response = await api.get(`/job/${jobId}/details`)
    return response.data
  },

  getResumeInfo: async (jobId: string): Promise<ResumeInfo> => {
    const response = await api.get(`/job/${jobId}/resume-info`)
    return response.data
  },

  getSectionDetails: async (jobId: string, sectionIndex: number): Promise<SectionDetails> => {
    const response = await api.get(`/job/${jobId}/section/${sectionIndex}`)
    return response.data
  },

  listAllJobs: async (): Promise<GalleryJob[]> => {
    const response = await api.get('/jobs')
    return response.data.jobs
  },

  listCompletedJobs: async (): Promise<GalleryJob[]> => {
    const response = await api.get('/jobs/completed')
    return response.data.jobs
  },

  deleteJob: async (jobId: string): Promise<void> => {
    await api.delete(`/job/${jobId}`)
  },

  deleteFailedJobs: async (): Promise<{ deleted_count: number }> => {
    const response = await api.delete('/jobs/failed')
    return response.data
  },

  getJobScript: async (jobId: string): Promise<any> => {
    const response = await api.get(`/job/${jobId}/script`)
    return response.data
  },

  getJobSections: async (jobId: string): Promise<SectionEdit[]> => {
    const response = await api.get(`/job/${jobId}/sections`)
    return response.data.sections
  },

  updateSectionCode: async (jobId: string, sectionId: string, code: string): Promise<void> => {
    await api.put(`/job/${jobId}/section/${sectionId}/code`, { manim_code: code })
  },

  regenerateSection: async (jobId: string, sectionId: string): Promise<void> => {
    await api.post(`/job/${jobId}/section/${sectionId}/regenerate`)
  },

  fixSection: async (jobId: string, sectionId: string, error: string, code: string): Promise<{ fixed_code: string }> => {
    const response = await api.post<{ fixed_code: string }>(`/job/${jobId}/section/${sectionId}/fix`, { 
      error, 
      manim_code: code 
    })
    return response.data
  },

  recompileJob: async (jobId: string): Promise<void> => {
    await api.post(`/job/${jobId}/recompile`)
  },

  compileHighQuality: async (jobId: string, quality: string): Promise<{ hq_job_id: string }> => {
    const response = await api.post<{ hq_job_id: string }>(`/job/${jobId}/compile-high-quality`, { quality })
    return response.data
  }
}
