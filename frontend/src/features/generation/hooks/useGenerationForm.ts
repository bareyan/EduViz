import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { generationService } from '../../../services/generation.service'
import { storageService } from '../../../services/storage.service'
import { AnalysisResult } from '../../../types/analysis.types'

export function useGenerationForm(analysis: AnalysisResult | null, selectedTopics: number[]) {
  const navigate = useNavigate()
  const [selectedLanguage, setSelectedLanguage] = useState('auto')
  const [selectedVoice, setSelectedVoice] = useState('')
  const [style, setStyle] = useState('3b1b')
  const [videoMode, setVideoMode] = useState<'comprehensive' | 'overview'>('comprehensive')
  const [contentFocus, setContentFocus] = useState<'practice' | 'theory' | 'as_document'>('as_document')
  const [documentContext, setDocumentContext] = useState<'standalone' | 'series' | 'auto'>('auto')
  const [isGenerating, setIsGenerating] = useState(false)

  const handleGenerate = async (finalVoice: string) => {
    if (!analysis) {
      toast.error('No analysis data found')
      return
    }

    setIsGenerating(true)

    try {
      const resumeJobId = storageService.getResumeJobId()
      
      const result = await generationService.generateVideos({
        file_id: analysis.file_id,
        analysis_id: analysis.analysis_id,
        selected_topics: selectedTopics,
        style,
        voice: finalVoice || selectedVoice,
        video_mode: videoMode,
        language: selectedLanguage,
        content_focus: contentFocus,
        document_context: documentContext,
        resume_job_id: resumeJobId || undefined,
      })
      
      storageService.clearResumeJobId()
      toast.success(resumeJobId ? 'Resuming video generation!' : 'Video generation started!')
      navigate(`/results/${result.job_id}`)
    } catch (error) {
      console.error('Generation failed:', error)
      toast.error('Failed to start generation')
      setIsGenerating(false)
    }
  }

  return {
    selectedLanguage, setSelectedLanguage,
    selectedVoice, setSelectedVoice,
    style, setStyle,
    videoMode, setVideoMode,
    contentFocus, setContentFocus,
    documentContext, setDocumentContext,
    isGenerating,
    handleGenerate
  }
}
