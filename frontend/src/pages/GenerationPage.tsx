import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loader2, Settings, Mic, Palette, ChevronRight, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { generateVideos, getVoices, Voice, AnalysisResult } from '../api'

export default function GenerationPage() {
  const { analysisId } = useParams<{ analysisId: string }>()
  const navigate = useNavigate()
  
  const [voices, setVoices] = useState<Voice[]>([])
  const [selectedVoice, setSelectedVoice] = useState('en-US-GuyNeural')
  const [style, setStyle] = useState('3b1b')
  const [maxLength, setMaxLength] = useState(20)
  const [isGenerating, setIsGenerating] = useState(false)

  // Retrieve stored data
  const selectedTopics: number[] = JSON.parse(sessionStorage.getItem('selectedTopics') || '[]')
  const analysis: AnalysisResult | null = JSON.parse(sessionStorage.getItem('analysis') || 'null')

  useEffect(() => {
    const loadVoices = async () => {
      try {
        const voiceList = await getVoices()
        setVoices(voiceList)
      } catch (error) {
        console.error('Failed to load voices:', error)
      }
    }
    loadVoices()
  }, [])

  const handleGenerate = async () => {
    if (!analysis) {
      toast.error('No analysis data found')
      return
    }

    setIsGenerating(true)

    try {
      const result = await generateVideos({
        file_id: analysis.file_id,
        analysis_id: analysis.analysis_id,
        selected_topics: selectedTopics,
        style,
        max_video_length: maxLength,
        voice: selectedVoice,
      })

      toast.success('Video generation started!')
      navigate(`/results/${result.job_id}`)
    } catch (error) {
      console.error('Generation failed:', error)
      toast.error('Failed to start generation')
      setIsGenerating(false)
    }
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <p className="text-gray-400">No analysis data found. Please start over.</p>
        <button
          onClick={() => navigate('/')}
          className="px-6 py-3 bg-math-blue text-white rounded-lg hover:bg-math-blue/80 transition-colors"
        >
          Go Home
        </button>
      </div>
    )
  }

  const selectedTopicData = analysis.suggested_topics.filter(t => selectedTopics.includes(t.index))
  const totalDuration = selectedTopicData.reduce((sum, t) => sum + t.estimated_duration, 0)

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Analysis
        </button>
        <h1 className="text-3xl font-bold mb-2">Customize Your Videos</h1>
        <p className="text-gray-400">
          Configure style, voice, and other settings before generating.
        </p>
      </div>

      {/* Summary Card */}
      <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
        <h2 className="text-lg font-semibold mb-4">Generation Summary</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Topics Selected</p>
            <p className="text-xl font-bold">{selectedTopics.length}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Estimated Duration</p>
            <p className="text-xl font-bold">~{totalDuration} min</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {selectedTopicData.map(topic => (
            <span 
              key={topic.index}
              className="px-3 py-1 bg-math-blue/20 text-math-blue rounded-full text-sm"
            >
              {topic.title}
            </span>
          ))}
        </div>
      </div>

      {/* Settings */}
      <div className="space-y-6">
        {/* Voice Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-purple/20 rounded-lg">
              <Mic className="w-5 h-5 text-math-purple" />
            </div>
            <h2 className="text-lg font-semibold">Voice Narration</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {voices.map(voice => (
              <button
                key={voice.id}
                onClick={() => setSelectedVoice(voice.id)}
                className={`
                  p-3 rounded-lg text-left transition-all
                  ${selectedVoice === voice.id 
                    ? 'bg-math-purple/20 border-math-purple border' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <p className="font-medium">{voice.name}</p>
                <p className="text-sm text-gray-500 capitalize">{voice.gender}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Style Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-green/20 rounded-lg">
              <Palette className="w-5 h-5 text-math-green" />
            </div>
            <h2 className="text-lg font-semibold">Animation Style</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { id: '3b1b', name: '3Blue1Brown', desc: 'Classic dark theme with blue accents' },
              { id: 'clean', name: 'Clean White', desc: 'Light theme for presentations' },
            ].map(s => (
              <button
                key={s.id}
                onClick={() => setStyle(s.id)}
                className={`
                  p-3 rounded-lg text-left transition-all
                  ${style === s.id 
                    ? 'bg-math-green/20 border-math-green border' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <p className="font-medium">{s.name}</p>
                <p className="text-sm text-gray-500">{s.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Max Length */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-orange/20 rounded-lg">
              <Settings className="w-5 h-5 text-math-orange" />
            </div>
            <h2 className="text-lg font-semibold">Video Settings</h2>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Maximum video length: {maxLength} minutes
            </label>
            <input
              type="range"
              min={5}
              max={30}
              value={maxLength}
              onChange={(e) => setMaxLength(Number(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
                         [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-math-orange 
                         [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>5 min</span>
              <span>30 min</span>
            </div>
          </div>
        </div>
      </div>

      {/* Generate Button */}
      <div className="flex justify-end">
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-math-blue to-math-purple 
                     text-white rounded-xl font-semibold text-lg hover:opacity-90 transition-opacity
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Starting Generation...
            </>
          ) : (
            <>
              Generate Videos
              <ChevronRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}
