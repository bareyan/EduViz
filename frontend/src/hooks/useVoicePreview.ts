import { useState, useRef, useEffect } from 'react'
import { API_BASE } from '../config/api.config'

export function useVoicePreview() {
    const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null)
    const audioRef = useRef<HTMLAudioElement | null>(null)

    const handlePreview = (voiceId: string, previewUrl?: string) => {
        if (!previewUrl) return

        if (playingVoiceId === voiceId) {
            audioRef.current?.pause()
            setPlayingVoiceId(null)
            return
        }

        if (audioRef.current) {
            audioRef.current.pause()
        }

        const audio = new Audio(`${API_BASE}${previewUrl}`)
        audio.onended = () => setPlayingVoiceId(null)
        audio.onerror = () => {
            console.error(`Failed to play preview for ${voiceId}`)
            setPlayingVoiceId(null)
        }
        audio.play().catch(err => {
            console.error("Audio playback failed:", err)
            setPlayingVoiceId(null)
        })
        audioRef.current = audio
        setPlayingVoiceId(voiceId)
    }

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (audioRef.current) {
                audioRef.current.pause()
            }
        }
    }, [])

    return { playingVoiceId, handlePreview }
}
