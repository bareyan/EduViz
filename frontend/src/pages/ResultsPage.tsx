import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  Download, 
  Play, 
  Home,
  Globe,
  Languages,
  Plus
} from 'lucide-react'
import toast from 'react-hot-toast'
import { GeneratedVideo, SectionProgress } from '../types/job.types'
import { generationService } from '../services/generation.service'
import { API_BASE } from '../config/api.config'
import { jobService } from '../services/job.service'
import { useJobProgress } from '../hooks/useJobProgress'
import { useTranslation } from '../hooks/useTranslation'
import { useVoices } from '../hooks/useVoices'
import { ResultsPageInProgress } from '../features/results/components/ResultsPageInProgress'
import { ResultsPageFailed } from '../features/results/components/ResultsPageFailed'
import { getStatusInfo } from '../features/results/results.utils'
import { formatDuration } from '../utils/format.utils'

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  
  const { job, detailedProgress, error } = useJobProgress(jobId)
  const { translations, translationLanguages, isTranslating, handleTranslate } = useTranslation(jobId)
  const { voices: translationVoices } = useVoices('auto')

  const [selectedVideo, setSelectedVideo] = useState<GeneratedVideo | null>(null)
  const [showTranslationModal, setShowTranslationModal] = useState(false)
  const [selectedLanguage, setSelectedLanguage] = useState('')
  const [selectedVoice, setSelectedVoice] = useState('')
  
  // Resume state
  const [resumeInfo, setResumeInfo] = useState<any | null>(null)
  const [isResuming, setIsResuming] = useState(false)
  
  // High quality compile state
  const [isCompilingHQ, setIsCompilingHQ] = useState(false)

  // Section modal state
  const [selectedSection, setSelectedSection] = useState<SectionProgress | null>(null)

  const getLanguageLabel = (code: string) =>
    translationLanguages.find(l => l.code === code)?.name || code

  useEffect(() => {
    if (job?.status === 'completed' && job.result && job.result.length > 0) {
      setSelectedVideo(job.result[0])
    }
    if (job?.status === 'failed' && jobId) {
      jobService.getResumeInfo(jobId).then(setResumeInfo).catch(console.error)
    }
  }, [job?.status, job?.result, jobId])

  // Handle translation creation
  const handleCreateTranslation = async () => {
    if (!jobId || !selectedLanguage) return
    await handleTranslate(selectedLanguage, selectedVoice)
    setShowTranslationModal(false)
    setSelectedLanguage('')
  }

  const handleCompileHighQuality = async (quality: 'medium' | 'high' | '4k' = 'high') => {
    if (!jobId) return
    
    setIsCompilingHQ(true)
    try {
      const data = await jobService.compileHighQuality(jobId, quality)
      toast.success(`${quality.toUpperCase()} quality compilation started!`)
      
      setTimeout(() => {
        navigate(`/results/${data.hq_job_id}`)
      }, 1500)
    } catch (err) {
      console.error('Failed to compile high quality:', err)
      toast.error('Failed to start high quality compilation')
    } finally {
      setIsCompilingHQ(false)
    }
  }

  const statusInfo = getStatusInfo(job?.status)

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <XCircle className="w-16 h-16 text-red-500" />
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">Error</h2>
          <p className="text-gray-400">{error}</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 px-6 py-3 bg-math-blue text-white rounded-lg 
                     hover:bg-math-blue/80 transition-colors"
        >
          <Home className="w-5 h-5" />
          Go Home
        </button>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <Loader2 className="w-16 h-16 text-math-blue animate-spin" />
        <p className="text-gray-400">Loading...</p>
      </div>
    )
  }

  // In Progress View
  if (job.status !== 'completed' && job.status !== 'failed') {
    return (
      <ResultsPageInProgress 
        job={job}
        jobId={jobId ?? ''}
        statusInfo={statusInfo}
        detailedProgress={detailedProgress}
        selectedSection={selectedSection}
        setSelectedSection={setSelectedSection}
      />
    )
  }

  // Failed View
  if (job.status === 'failed') {
    const handleResume = async () => {
      if (!jobId) return
      setIsResuming(true)
      try {
        const analysis = JSON.parse(sessionStorage.getItem('analysis') || 'null')
        const selectedTopics = JSON.parse(sessionStorage.getItem('selectedTopics') || '[]')
        
        if (!analysis || selectedTopics.length === 0) {
          toast.error('Original generation data not found. Please start a new generation from the Gallery.')
          return
        }
        
        sessionStorage.setItem('resumeJobId', jobId)
        navigate(`/generate/${analysis.analysis_id}`)
      } catch (err) {
        console.error('Failed to resume:', err)
        toast.error('Failed to resume generation')
      } finally {
        setIsResuming(false)
      }
    }
    
    return (
      <ResultsPageFailed 
        job={job}
        resumeInfo={resumeInfo}
        isResuming={isResuming}
        handleResume={handleResume}
        onGoHome={() => navigate('/')}
        onRetry={() => window.location.reload()}
      />
    )
  }

  // Completed View
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <CheckCircle className="w-8 h-8 text-math-green" />
            <h1 className="text-3xl font-bold">Videos Ready!</h1>
          </div>
          <p className="text-gray-400">
            {job.result?.length} video{job.result?.length !== 1 ? 's' : ''} generated successfully
          </p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-white rounded-lg 
                     hover:bg-gray-700 transition-colors"
        >
          <Home className="w-5 h-5" />
          New Project
        </button>
      </div>

      {/* Main Content */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Video Player */}
        <div className="lg:col-span-2">
          {selectedVideo && (
            <VideoPlayer video={selectedVideo} />
          )}
        </div>

        {/* Video List */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Generated Videos</h2>
          <div className="space-y-3">
            {job.result?.map(video => (
              <VideoCard
                key={video.video_id}
                video={video}
                isSelected={selectedVideo?.video_id === video.video_id}
                onSelect={() => setSelectedVideo(video)}
              />
            ))}
          </div>
          
          {/* Translations Section */}
          <div className="mt-6 pt-6 border-t border-gray-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Languages className="w-5 h-5 text-math-purple" />
                <h2 className="text-lg font-semibold">Translations</h2>
              </div>
              <button
                onClick={() => setShowTranslationModal(true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-math-purple/20 text-math-purple 
                           rounded-lg hover:bg-math-purple/30 transition-colors text-sm"
              >
                <Plus className="w-4 h-4" />
                Add Translation
              </button>
            </div>
            
            {translations && (
              <p className="text-sm text-gray-500 mb-3">
                Original: {getLanguageLabel(translations.original_language)}
              </p>
            )}
            
            <div className="space-y-2">
              {translations?.translations.map(t => (
                <div 
                  key={t.language}
                  className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-gray-400" />
                    <span>{getLanguageLabel(t.language)}</span>
                  </div>
                  {t.has_video ? (
                    <a 
                      href={`${API_BASE}${t.video_url}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-sm text-math-blue hover:underline"
                    >
                      <Play className="w-3 h-3" />
                      Watch
                    </a>
                  ) : (
                    <span className="flex items-center gap-1 text-sm text-gray-500">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Processing...
                    </span>
                  )}
                </div>
              ))}
              
              {(!translations || translations.translations.length === 0) && (
                <p className="text-sm text-gray-500 text-center py-4">
                  No translations yet. Click "Add Translation" to create one.
                </p>
              )}
            </div>
          </div>
          
          <div className="mt-6 pt-6 border-t border-gray-800">
            <h2 className="text-lg font-semibold mb-3">Quality Options</h2>
            <div className="space-y-2">
              <button
                onClick={() => handleCompileHighQuality('high')}
                disabled={isCompilingHQ}
                className="w-full flex items-center justify-between p-3 bg-gradient-to-r from-purple-600 to-pink-600 
                           text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                <span className="flex items-center gap-2">
                  <Play className="w-4 h-4" />
                  Compile in High Quality (1080p)
                </span>
                {isCompilingHQ && <Loader2 className="w-4 h-4 animate-spin" />}
              </button>
              <p className="text-xs text-gray-500 px-3">
                Re-render the entire video in high quality. This will take longer but produce better results.
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {showTranslationModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-xl p-6 max-w-md w-full mx-4 border border-gray-800">
            <h3 className="text-xl font-semibold mb-4">Add Translation</h3>
            <p className="text-gray-400 text-sm mb-4">
              Select a language to translate the video into. The narration will be translated and 
              new audio will be generated.
            </p>
            
            <label className="block text-sm font-medium text-gray-300 mb-2">Target Language</label>
            <div className="space-y-2 max-h-40 overflow-y-auto mb-4">
              {translationLanguages
                .filter(lang => lang.code !== translations?.original_language)
                .filter(lang => !translations?.translations.some(t => t.language === lang.code))
                .map(lang => (
                  <button
                    key={lang.code}
                    onClick={() => setSelectedLanguage(lang.code)}
                    className={`w-full p-3 rounded-lg text-left transition-all ${
                      selectedLanguage === lang.code
                        ? 'bg-math-purple/20 border-math-purple border'
                        : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                    }`}
                  >
                    {lang.name}
                  </button>
                ))}
            </div>
            
            <label className="block text-sm font-medium text-gray-300 mb-2">Voice</label>
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="w-full p-3 rounded-lg bg-gray-800 border border-gray-700 text-white mb-4
                         focus:outline-none focus:border-math-purple"
            >
              {translationVoices.map(voice => (
                <option key={voice.id} value={voice.id}>
                  {voice.name} ({voice.gender})
                </option>
              ))}
            </select>
            
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowTranslationModal(false)
                  setSelectedLanguage('')
                }}
                className="flex-1 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTranslation}
                disabled={!selectedLanguage || isTranslating}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-math-purple text-white 
                           rounded-lg hover:bg-math-purple/80 transition-colors disabled:opacity-50"
              >
                {isTranslating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Starting...
                  </>
                ) : (
                  'Start Translation'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function VideoPlayer({ video }: { video: GeneratedVideo }) {
  const videoUrl = video.download_url 
    ? (video.download_url.startsWith('http') ? video.download_url : `${API_BASE}${video.download_url}`)
    : generationService.getVideoUrl(video.video_id)

  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = videoUrl
    a.download = `${video.title || 'video'}.mp4`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    toast.success('Download started!')
  }

  const chapters = video.chapters || []

  return (
    <div className="rounded-xl overflow-hidden bg-gray-900 border border-gray-800">
      <div className="aspect-video bg-black relative">
        <video
          src={videoUrl}
          className="w-full h-full"
          controls
        />
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold mb-1">{video.title}</h3>
            <p className="text-sm text-gray-500">
              {formatDuration(video.duration)} • {chapters.length} chapters
            </p>
          </div>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-2 bg-math-blue text-white rounded-lg 
                       hover:bg-math-blue/80 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
        </div>

        {chapters.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-400 mb-2">Chapters</h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {chapters.map((chapter, i) => (
                <div 
                  key={i}
                  className="flex items-center gap-3 p-2 bg-gray-800/50 rounded-lg text-sm"
                >
                  <span className="text-gray-500">{formatDuration(chapter.start_time)}</span>
                  <span className="flex-1">{chapter.title}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function VideoCard({ 
  video, 
  isSelected, 
  onSelect 
}: { 
  video: GeneratedVideo
  isSelected: boolean
  onSelect: () => void 
}) {
  return (
    <div
      onClick={onSelect}
      className={`
        p-4 rounded-xl cursor-pointer transition-all
        ${isSelected 
          ? 'bg-math-blue/20 border-math-blue border' 
          : 'bg-gray-900/50 border-gray-800 border hover:border-gray-700'
        }
      `}
    >
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-lg bg-gray-800 flex items-center justify-center">
          <Play className="w-5 h-5 text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium truncate">{video.title}</h3>
          <p className="text-sm text-gray-500">{formatDuration(video.duration)}</p>
        </div>
      </div>
    </div>
  )
}
