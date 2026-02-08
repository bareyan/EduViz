import { useState, useEffect, useRef } from 'react'
import { analysisService } from '../services/analysis.service'
import { storageService } from '../services/storage.service'
import { AnalysisResult } from '../types/analysis.types'
import toast from 'react-hot-toast'

export function useAnalysis(fileId: string | undefined) {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [selectedTopics, setSelectedTopics] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const hasAnalyzed = useRef(false)

  useEffect(() => {
    if (!fileId || hasAnalyzed.current) return
    hasAnalyzed.current = true

    const runAnalysis = async () => {
      try {
        setIsLoading(true)
        const result = await analysisService.analyzeFile(fileId)
        setAnalysis(result)
        setSelectedTopics(result.suggested_topics.map(t => t.index))
      } catch (err) {
        console.error('Analysis failed:', err)
        setError('Failed to analyze the file. Please try again.')
        toast.error('Analysis failed')
      } finally {
        setIsLoading(false)
      }
    }

    runAnalysis()
  }, [fileId])

  const toggleTopic = (index: number) => {
    setSelectedTopics(prev => 
      prev.includes(index) 
        ? prev.filter(i => i !== index)
        : [...prev, index]
    )
  }

  const saveToStorage = () => {
    if (analysis) {
      storageService.setAnalysis(analysis)
      storageService.setSelectedTopics(selectedTopics)
    }
  }

  return { analysis, selectedTopics, isLoading, error, toggleTopic, saveToStorage }
}
