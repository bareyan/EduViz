import api from '../config/api.config'
import { TranslationsResponse, TranslationResponse, TranslationLanguagesResponse } from '../types/translation.types'

export const translationService = {
  getJobTranslations: async (jobId: string): Promise<TranslationsResponse> => {
    const response = await api.get(`/job/${jobId}/translations`)
    return response.data
  },

  createTranslation: async (jobId: string, targetLanguage: string, voice?: string): Promise<TranslationResponse> => {
    const response = await api.post(`/job/${jobId}/translate`, { 
      target_language: targetLanguage,
      voice: voice 
    })
    return response.data
  },

  getTranslationLanguages: async (): Promise<TranslationLanguagesResponse> => {
    const response = await api.get('/translation/languages')
    return response.data
  }
}
