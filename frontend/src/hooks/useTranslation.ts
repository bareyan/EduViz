import { useState, useEffect } from 'react'
import { translationService } from '../services/translation.service'
import { TranslationsResponse, TranslationLanguage } from '../types/translation.types'
import toast from 'react-hot-toast'

export function useTranslation(jobId: string | undefined) {
  const [translations, setTranslations] = useState<TranslationsResponse | null>(null)
  const [translationLanguages, setTranslationLanguages] = useState<TranslationLanguage[]>([])
  const [isTranslating, setIsTranslating] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const fetchTranslations = async () => {
    if (!jobId) return
    try {
      const data = await translationService.getJobTranslations(jobId)
      setTranslations(data)
    } catch (err) {
      console.error('Failed to fetch translations:', err)
    }
  }

  const fetchLanguages = async () => {
    try {
      const data = await translationService.getTranslationLanguages()
      setTranslationLanguages(data.languages)
    } catch (err) {
      console.error('Failed to fetch translation languages:', err)
    }
  }

  const handleTranslate = async (targetLanguage: string, voice?: string) => {
    if (!jobId) return
    setIsTranslating(true)
    try {
      await translationService.createTranslation(jobId, targetLanguage, voice)
      toast.success('Translation started!')
      await fetchTranslations()
    } catch (err) {
      console.error('Translation failed:', err)
      toast.error('Failed to start translation')
    } finally {
      setIsTranslating(false)
    }
  }

  useEffect(() => {
    if (jobId) {
      setIsLoading(true)
      Promise.all([fetchTranslations(), fetchLanguages()]).finally(() => setIsLoading(false))
    }
  }, [jobId])

  return {
    translations,
    translationLanguages,
    isTranslating,
    isLoading,
    handleTranslate,
    refreshTranslations: fetchTranslations
  }
}
