import api from '../config/api.config'
import { VoicesResponse } from '../types/voice.types'

export const voiceService = {
  getVoices: async (language: string = 'en'): Promise<VoicesResponse> => {
    const response = await api.get(`/voices?language=${language}`)
    return response.data
  }
}