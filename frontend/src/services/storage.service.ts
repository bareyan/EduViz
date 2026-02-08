import { AnalysisResult } from '../types/analysis.types'

const KEYS = {
  ANALYSIS: 'analysis',
  SELECTED_TOPICS: 'selectedTopics',
  RESUME_JOB_ID: 'resumeJobId',
}

export const storageService = {
  getAnalysis: (): AnalysisResult | null => {
    const data = sessionStorage.getItem(KEYS.ANALYSIS)
    return data ? JSON.parse(data) : null
  },
  setAnalysis: (analysis: AnalysisResult) => {
    sessionStorage.setItem(KEYS.ANALYSIS, JSON.stringify(analysis))
  },
  getSelectedTopics: (): number[] => {
    const data = sessionStorage.getItem(KEYS.SELECTED_TOPICS)
    return data ? JSON.parse(data) : []
  },
  setSelectedTopics: (topics: number[]) => {
    sessionStorage.setItem(KEYS.SELECTED_TOPICS, JSON.stringify(topics))
  },
  getResumeJobId: (): string | null => {
    return sessionStorage.getItem(KEYS.RESUME_JOB_ID)
  },
  setResumeJobId: (jobId: string) => {
    sessionStorage.setItem(KEYS.RESUME_JOB_ID, jobId)
  },
  clearResumeJobId: () => {
    sessionStorage.removeItem(KEYS.RESUME_JOB_ID)
  },
  clearAll: () => {
    sessionStorage.removeItem(KEYS.ANALYSIS)
    sessionStorage.removeItem(KEYS.SELECTED_TOPICS)
    sessionStorage.removeItem(KEYS.RESUME_JOB_ID)
  }
}
