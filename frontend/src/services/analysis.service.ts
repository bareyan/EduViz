import api from '../config/api.config'
import { UploadResponse, AnalysisResult } from '../types/analysis.types'

export const analysisService = {
  uploadFile: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await api.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  analyzeFile: async (fileId: string): Promise<AnalysisResult> => {
    const response = await api.post('/analyze', { file_id: fileId })
    return response.data
  },

  deleteFile: async (fileId: string): Promise<void> => {
    await api.delete(`/file/${fileId}`)
  }
}
