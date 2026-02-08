import { useState, useEffect } from 'react'
import { voiceService } from '../services/voice.service'
import { Voice, Language } from '../types/voice.types'

export function useVoices(selectedLanguage: string = 'en') {
  const [voices, setVoices] = useState<Voice[]>([])
  const [languages, setLanguages] = useState<Language[]>([])
  const [selectedVoice, setSelectedVoice] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    const loadVoices = async () => {
      setIsLoading(true)
      try {
        const data = await voiceService.getVoices(selectedLanguage)
        if (!isMounted) return
        
        setVoices(data.voices)
        setLanguages(data.languages)
        
        if (data.default_voice) {
          setSelectedVoice(data.default_voice)
        } else if (data.voices.length > 0) {
          setSelectedVoice(data.voices[0].id)
        }
      } catch (err) {
        if (!isMounted) return
        setError(err instanceof Error ? err : new Error('Failed to load voices'))
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    loadVoices()
    return () => {
      isMounted = false
    }
  }, [selectedLanguage])

  return { voices, languages, selectedVoice, setSelectedVoice, isLoading, error }
}
