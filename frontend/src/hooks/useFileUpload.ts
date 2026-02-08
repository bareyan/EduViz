import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { analysisService } from '../services/analysis.service'

export function useFileUpload() {
  const navigate = useNavigate()
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  const upload = useCallback(async (file: File) => {
    setIsUploading(true)
    setUploadProgress(0)

    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)

      const result = await analysisService.uploadFile(file)
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      toast.success('File uploaded successfully!')
      navigate(`/analysis/${result.file_id}`)
    } catch (error) {
      console.error('Upload failed:', error)
      toast.error('Failed to upload file. Please try again.')
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }, [navigate])

  return { upload, isUploading, uploadProgress }
}
