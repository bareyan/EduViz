import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loader2, Palette, ChevronRight, ArrowLeft, Clock, Zap, Globe, BookOpen, GraduationCap, FileText, Link2, Layers, RotateCcw, Cpu } from 'lucide-react'
import toast from 'react-hot-toast'
import { generateVideos, getVoices, Voice, Language, AnalysisResult, getPipelines, PipelineInfo } from '../api'

export default function GenerationPage() {
  const { analysisId: _analysisId } = useParams<{ analysisId: string }>()
  const navigate = useNavigate()
  
  const [languages, setLanguages] = useState<Language[]>([])
  const [selectedLanguage, setSelectedLanguage] = useState('auto')  // Auto-detect from document
  const [voices, setVoices] = useState<Voice[]>([])
  const [selectedVoice, setSelectedVoice] = useState('')  // Will be set from API default
  const [style, setStyle] = useState('3b1b')
  const [videoMode, setVideoMode] = useState<'comprehensive' | 'overview'>('comprehensive')
  const [contentFocus, setContentFocus] = useState<'practice' | 'theory' | 'as_document'>('as_document')
  const [documentContext, setDocumentContext] = useState<'standalone' | 'series' | 'auto'>('auto')
  const [isGenerating, setIsGenerating] = useState(false)
  const [pipelines, setPipelines] = useState<PipelineInfo[]>([])
  const [selectedPipeline, setSelectedPipeline] = useState('default')
  
  // Check if we're resuming a previous job
  const resumeJobId = sessionStorage.getItem('resumeJobId')
  const isResuming = !!resumeJobId

  // Retrieve stored data
  const selectedTopics: number[] = JSON.parse(sessionStorage.getItem('selectedTopics') || '[]')
  const analysis: AnalysisResult | null = JSON.parse(sessionStorage.getItem('analysis') || 'null')

  // Load available pipelines
  useEffect(() => {
    const loadPipelines = async () => {
      try {
        const data = await getPipelines()
        setPipelines(data.pipelines)
        // Set active pipeline as default
        if (data.active) {
          setSelectedPipeline(data.active)
        }
      } catch (error) {
        console.error('Failed to load pipelines:', error)
      }
    }
    loadPipelines()
  }, [])

  // Load voices when language changes
  useEffect(() => {
    const loadVoices = async () => {
      try {
        // For auto mode, load multilingual voices (backend now supports 'auto' as a language code)
        const data = await getVoices(selectedLanguage)
        setVoices(data.voices)
        setLanguages(data.languages)
        // Set default voice for the language (from API)
        if (data.default_voice) {
          setSelectedVoice(data.default_voice)
        } else if (data.voices.length > 0) {
          setSelectedVoice(data.voices[0].id)
        }
      } catch (error) {
        console.error('Failed to load voices:', error)
      }
    }
    loadVoices()
  }, [selectedLanguage])

  const handleGenerate = async () => {
    if (!analysis) {
      toast.error('No analysis data found')
      return
    }

    setIsGenerating(true)

    try {
      // Check if we're resuming a previous job
      const resumeJobId = sessionStorage.getItem('resumeJobId')
      
      const result = await generateVideos({
        file_id: analysis.file_id,
        analysis_id: analysis.analysis_id,
        selected_topics: selectedTopics,
        style,
        voice: selectedVoice,
        video_mode: videoMode,
        language: selectedLanguage,
        content_focus: contentFocus,
        document_context: documentContext,
        pipeline: selectedPipeline,
        resume_job_id: resumeJobId || undefined,
      })
      
      // Clear resume job ID after use
      sessionStorage.removeItem('resumeJobId')

      toast.success(resumeJobId ? 'Resuming video generation!' : 'Video generation started!')
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
            <p className="text-xl font-bold">
              ~{videoMode === 'overview' ? Math.round(totalDuration / 3) : totalDuration} min
              {videoMode === 'overview' && <span className="text-sm text-gray-500"> (overview)</span>}
            </p>
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
        {/* Video Mode Selection - NEW */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-blue/20 rounded-lg">
              <Clock className="w-5 h-5 text-math-blue" />
            </div>
            <h2 className="text-lg font-semibold">Video Mode</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setVideoMode('comprehensive')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${videoMode === 'comprehensive' 
                  ? 'bg-math-blue/20 border-math-blue border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-5 h-5" />
                <p className="font-semibold">Comprehensive</p>
              </div>
              <p className="text-sm text-gray-400">
                Full detailed coverage with all proofs, examples, and explanations. 
                Longer videos (~15-45 min).
              </p>
            </button>
            <button
              onClick={() => setVideoMode('overview')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${videoMode === 'overview' 
                  ? 'bg-math-orange/20 border-math-orange border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-5 h-5" />
                <p className="font-semibold">Quick Overview</p>
              </div>
              <p className="text-sm text-gray-400">
                Fast summary covering key concepts and main ideas.
                Shorter videos (~3-7 min).
              </p>
            </button>
          </div>
        </div>

        {/* Content Focus Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-orange/20 rounded-lg">
              <BookOpen className="w-5 h-5 text-math-orange" />
            </div>
            <h2 className="text-lg font-semibold">Content Focus</h2>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Choose how the video should balance examples and theory
          </p>
          <div className="grid grid-cols-3 gap-3">
            <button
              onClick={() => setContentFocus('as_document')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${contentFocus === 'as_document' 
                  ? 'bg-math-orange/20 border-math-orange border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-5 h-5" />
                <p className="font-semibold">As Document</p>
              </div>
              <p className="text-sm text-gray-400">
                Follow the document's natural structure and balance
              </p>
            </button>
            <button
              onClick={() => setContentFocus('practice')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${contentFocus === 'practice' 
                  ? 'bg-math-green/20 border-math-green border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <GraduationCap className="w-5 h-5" />
                <p className="font-semibold">Practice</p>
              </div>
              <p className="text-sm text-gray-400">
                More examples, worked problems, and applications
              </p>
            </button>
            <button
              onClick={() => setContentFocus('theory')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${contentFocus === 'theory' 
                  ? 'bg-math-purple/20 border-math-purple border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <BookOpen className="w-5 h-5" />
                <p className="font-semibold">Theory</p>
              </div>
              <p className="text-sm text-gray-400">
                More proofs, derivations, and conceptual depth
              </p>
            </button>
          </div>
        </div>

        {/* Document Context Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-teal-500/20 rounded-lg">
              <Layers className="w-5 h-5 text-teal-400" />
            </div>
            <h2 className="text-lg font-semibold">Document Context</h2>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Is this document standalone or part of a series (like a textbook chapter)?
          </p>
          <div className="grid grid-cols-3 gap-3">
            <button
              onClick={() => setDocumentContext('auto')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${documentContext === 'auto' 
                  ? 'bg-teal-500/20 border-teal-400 border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-5 h-5" />
                <p className="font-semibold">Auto-detect</p>
              </div>
              <p className="text-sm text-gray-400">
                AI will analyze the document and decide
              </p>
            </button>
            <button
              onClick={() => setDocumentContext('standalone')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${documentContext === 'standalone' 
                  ? 'bg-math-blue/20 border-math-blue border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-5 h-5" />
                <p className="font-semibold">Standalone</p>
              </div>
              <p className="text-sm text-gray-400">
                Explain all concepts - assume no prior knowledge
              </p>
            </button>
            <button
              onClick={() => setDocumentContext('series')}
              className={`
                p-4 rounded-lg text-left transition-all
                ${documentContext === 'series' 
                  ? 'bg-math-purple/20 border-math-purple border-2' 
                  : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-center gap-2 mb-2">
                <Link2 className="w-5 h-5" />
                <p className="font-semibold">Part of Series</p>
              </div>
              <p className="text-sm text-gray-400">
                Prior concepts from the series can be assumed known
              </p>
            </button>
          </div>
        </div>

        {/* Pipeline Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-500/20 rounded-lg">
              <Cpu className="w-5 h-5 text-indigo-400" />
            </div>
            <h2 className="text-lg font-semibold">AI Model Pipeline</h2>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Choose the AI models used for script generation and video creation
          </p>
          <div className="space-y-3">
            {pipelines.map(pipeline => (
              <button
                key={pipeline.name}
                onClick={() => setSelectedPipeline(pipeline.name)}
                className={`
                  w-full p-4 rounded-lg text-left transition-all
                  ${selectedPipeline === pipeline.name
                    ? 'bg-indigo-500/20 border-indigo-400 border-2' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="font-semibold capitalize">
                    {pipeline.name.replace('_', ' ')}
                  </p>
                  {pipeline.is_active && (
                    <span className="text-xs px-2 py-1 bg-indigo-500/20 text-indigo-400 rounded">
                      Active
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-400 mb-2">
                  {pipeline.description}
                </p>
                <div className="text-xs text-gray-500 space-y-1">
                  <div>Script: {pipeline.models.script_generation}</div>
                  <div>Visual Script: {pipeline.models.visual_script_generation}</div>
                  <div>Manim: {pipeline.models.manim_generation}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Language & Voice Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-purple/20 rounded-lg">
              <Globe className="w-5 h-5 text-math-purple" />
            </div>
            <h2 className="text-lg font-semibold">Language & Voice</h2>
          </div>
          
          {/* Language Selection */}
          <div className="mb-4">
            <label className="text-sm text-gray-400 mb-2 block">Language</label>
            <div className="flex flex-wrap gap-3">
              {/* Auto option first */}
              <button
                onClick={() => setSelectedLanguage('auto')}
                className={`
                  px-4 py-2 rounded-lg font-medium transition-all
                  ${selectedLanguage === 'auto' 
                    ? 'bg-math-purple text-white' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                🌐 Auto (Document)
              </button>
              {languages.map(lang => (
                <button
                  key={lang.code}
                  onClick={() => setSelectedLanguage(lang.code)}
                  className={`
                    px-4 py-2 rounded-lg font-medium transition-all
                    ${selectedLanguage === lang.code 
                      ? 'bg-math-purple text-white' 
                      : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                    }
                  `}
                >
                  {lang.name}
                </button>
              ))}
            </div>
            {selectedLanguage === 'auto' && (
              <p className="text-xs text-gray-500 mt-2">
                The video will be generated in the document's original language. You can add translations later.
              </p>
            )}
          </div>
          
          {/* Voice Selection */}
          <label className="text-sm text-gray-400 mb-2 block">Voice</label>
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
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { id: '3b1b', name: '3Blue1Brown', desc: 'Classic dark theme with blue accents', color: 'bg-blue-900' },
              { id: 'clean', name: 'Clean White', desc: 'Light theme for presentations', color: 'bg-gray-100' },
              { id: 'dracula', name: 'Dracula', desc: 'Dark purple theme, popular in coding', color: 'bg-purple-900' },
              { id: 'solarized', name: 'Solarized', desc: 'Warm professional look', color: 'bg-teal-900' },
              { id: 'nord', name: 'Nord', desc: 'Cool arctic aesthetic', color: 'bg-slate-700' },
            ].map(s => (
              <button
                key={s.id}
                onClick={() => setStyle(s.id)}
                className={`
                  p-3 rounded-lg text-left transition-all relative overflow-hidden
                  ${style === s.id 
                    ? 'bg-math-green/20 border-math-green border-2' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <div className={`absolute top-2 right-2 w-4 h-4 rounded-full ${s.color} border border-gray-600`}></div>
                <p className="font-medium">{s.name}</p>
                <p className="text-sm text-gray-500 pr-6">{s.desc}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Resume Banner */}
      {isResuming && (
        <div className="bg-gradient-to-r from-math-green/20 to-teal-500/20 border border-math-green/50 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <RotateCcw className="w-5 h-5 text-math-green" />
            <div>
              <p className="font-medium text-math-green">Resuming Previous Generation</p>
              <p className="text-sm text-gray-400">
                Your previous generation will continue from where it stopped. Completed sections will be reused.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Generate Button */}
      <div className="flex justify-end">
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className={`flex items-center gap-2 px-8 py-4 
                     ${isResuming 
                       ? 'bg-gradient-to-r from-math-green to-teal-500' 
                       : 'bg-gradient-to-r from-math-blue to-math-purple'
                     }
                     text-white rounded-xl font-semibold text-lg hover:opacity-90 transition-opacity
                     disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              {isResuming ? 'Resuming...' : 'Starting Generation...'}
            </>
          ) : isResuming ? (
            <>
              <RotateCcw className="w-5 h-5" />
              Resume Generation
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
