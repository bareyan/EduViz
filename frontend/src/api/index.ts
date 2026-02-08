import api, { API_BASE } from '../config/api.config'
import { analysisService } from '../services/analysis.service'
import { generationService } from '../services/generation.service'
import { jobService } from '../services/job.service'
import { voiceService } from '../services/voice.service'
import { translationService } from '../services/translation.service'

export { jobService }
export { API_BASE as API_URL } from '../config/api.config'
export * from '../types/analysis.types'
export * from '../types/job.types'
export * from '../types/section.types'
export * from '../types/voice.types'
export * from '../types/pipeline.types'
export * from '../types/translation.types'

export { API_BASE }

// API Functions - Compatibility Layer
export const uploadFile = analysisService.uploadFile
export const analyzeFile = analysisService.analyzeFile
export const deleteFile = analysisService.deleteFile

export const getPipelines = generationService.getPipelines
export const generateVideos = generationService.generateVideos
export const getVideoUrl = generationService.getVideoUrl

export const getJobStatus = jobService.getJobStatus
export const getJobDetails = jobService.getJobDetails
export const getResumeInfo = jobService.getResumeInfo
export const getSectionDetails = jobService.getSectionDetails
export const listAllJobs = jobService.listAllJobs
export const listCompletedJobs = jobService.listCompletedJobs
export const deleteJob = jobService.deleteJob
export const deleteFailedJobs = jobService.deleteFailedJobs
export const getJobScript = jobService.getJobScript
export const getJobSections = jobService.getJobSections
export const updateSectionCode = jobService.updateSectionCode
export const recompileJob = jobService.recompileJob

export const getVoices = voiceService.getVoices

export const getJobTranslations = translationService.getJobTranslations
export const createTranslation = translationService.createTranslation
export const getTranslationLanguages = translationService.getTranslationLanguages

export default api
