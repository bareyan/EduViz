import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  Download, 
  Play, 
  Home,
  RefreshCw,
  Globe,
  Languages,
  Plus,
  RotateCcw
} from 'lucide-react'
import toast from 'react-hot-toast'
import { 
  getJobStatus, 
  getJobDetails,
  JobResponse, 
  GeneratedVideo, 
  getVideoUrl, 
  API_BASE,
  getJobTranslations,
  createTranslation,
  TranslationsResponse,
  AVAILABLE_LANGUAGES,
  MULTILINGUAL_VOICES,
  getResumeInfo,
  ResumeInfo,
  DetailedProgress,
  SectionProgress
} from '../api'
import { SectionProgressView, SectionScriptModal } from '../components/SectionProgressView'

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  
  const [job, setJob] = useState<JobResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedVideo, setSelectedVideo] = useState<GeneratedVideo | null>(null)
  
  // Translation state
  const [translations, setTranslations] = useState<TranslationsResponse | null>(null)
  const [showTranslationModal, setShowTranslationModal] = useState(false)
  const [selectedLanguage, setSelectedLanguage] = useState('')
  const [selectedVoice, setSelectedVoice] = useState(MULTILINGUAL_VOICES[0].id)
  const [isTranslating, setIsTranslating] = useState(false)
  
  // Resume state
  const [resumeInfo, setResumeInfo] = useState<ResumeInfo | null>(null)
  const [isResuming, setIsResuming] = useState(false)
  
  // High quality compile state
  const [isCompilingHQ, setIsCompilingHQ] = useState(false)
  const [hqJobId, setHqJobId] = useState<string | null>(null)

  // Detailed progress state
  const [detailedProgress, setDetailedProgress] = useState<DetailedProgress | null>(null)
  const [selectedSection, setSelectedSection] = useState<SectionProgress | null>(null)

  useEffect(() => {
    if (!jobId) return

    let isMounted = true
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const pollStatus = async () => {
      try {
        const [status, details] = await Promise.all([
          getJobStatus(jobId),
          getJobDetails(jobId).catch((err) => {
            console.warn('Failed to fetch detailed progress:', err)
            return null
          })
        ])
        
        if (!isMounted) return
        
        // Force update by creating a new object reference
        setJob({ ...status })
        
        // Update detailed progress if available
        if (details) {
          console.log('Detailed progress update:', {
            stage: details.current_stage,
            currentSection: details.current_section_index,
            completed: details.completed_sections,
            total: details.total_sections,
            sectionsArray: details.sections,
            sectionsIsArray: Array.isArray(details.sections),
            sectionsLength: details.sections?.length
          })
          setDetailedProgress({ ...details })
        }

        if (status.status === 'completed' && status.result && status.result.length > 0) {
          setSelectedVideo(status.result[0])
          // Fetch translations when job is complete
          fetchTranslations()
        }
        
        // Fetch resume info when job fails
        if (status.status === 'failed') {
          fetchResumeInfo()
        }

        // Continue polling if not completed or failed
        if (status.status !== 'completed' && status.status !== 'failed') {
          timeoutId = setTimeout(pollStatus, 1500)  // Poll every 1.5 seconds
        }
      } catch (err) {
        console.error('Failed to get job status:', err)
        if (isMounted) {
          setError('Failed to get job status')
        }
      }
    }
    
    const fetchTranslations = async () => {
      try {
        const data = await getJobTranslations(jobId)
        if (isMounted) {
          setTranslations(data)
        }
      } catch (err) {
        console.error('Failed to fetch translations:', err)
      }
    }
    
    const fetchResumeInfo = async () => {
      try {
        const info = await getResumeInfo(jobId)
        if (isMounted) {
          setResumeInfo(info)
        }
      } catch (err) {
        console.error('Failed to fetch resume info:', err)
      }
    }

    pollStatus()

    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [jobId])  // Only depend on jobId, not job.status
  
  // Handle translation creation
  const handleCreateTranslation = async () => {
    if (!jobId || !selectedLanguage) return
    
    setIsTranslating(true)
    try {
      await createTranslation(jobId, selectedLanguage, selectedVoice)
      toast.success(`Translation to ${AVAILABLE_LANGUAGES.find(l => l.code === selectedLanguage)?.name || selectedLanguage} started!`)
      setShowTranslationModal(false)
      setSelectedLanguage('')
      
      // Poll for translation completion
      const pollTranslations = setInterval(async () => {
        try {
          const data = await getJobTranslations(jobId)
          setTranslations(data)
          
          // Check if translation is complete
          const translation = data.translations.find(t => t.language === selectedLanguage)
          if (translation?.has_video) {
            clearInterval(pollTranslations)
            toast.success('Translation complete!')
          }
        } catch {
          // Ignore errors during polling
        }
      }, 3000)
      
      // Stop polling after 10 minutes
      setTimeout(() => clearInterval(pollTranslations), 600000)
      
    } catch (err) {
      console.error('Failed to create translation:', err)
      toast.error('Failed to start translation')
    } finally {
      setIsTranslating(false)
    }
  }
  
  // Handle high quality compilation
  const handleCompileHighQuality = async (quality: 'medium' | 'high' | '4k' = 'high') => {
    if (!jobId) return
    
    setIsCompilingHQ(true)
    try {
      const response = await fetch(`${API_BASE}/job/${jobId}/compile-high-quality`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality })
      })
      
      if (!response.ok) throw new Error('Failed to start high quality compilation')
      
      const data = await response.json()
      setHqJobId(data.hq_job_id)
      toast.success(`${quality.toUpperCase()} quality compilation started!`)
      
      // Navigate to the new HQ job
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
    // Updated stages to reflect actual workflow:
    // Script generation, then parallel audio+animation, then composing
    const stages = [
      { key: 'pending', label: 'Starting' },
      { key: 'analyzing', label: 'Analyzing' },
      { key: 'generating_script', label: 'Script' },
      { key: 'creating_animations', label: 'Creating Sections' },  // Audio + Animation happen together
      { key: 'composing_video', label: 'Composing' }
    ]
    
    return (
      <div className="max-w-2xl mx-auto">
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
          {/* Animated Logo */}
          <div className="relative">
            <div className="w-32 h-32 rounded-full border-4 border-math-blue/30 flex items-center justify-center">
              <div className="w-24 h-24 rounded-full border-4 border-t-math-blue border-r-transparent border-b-transparent border-l-transparent animate-spin" />
            </div>
            <div className={`absolute inset-0 flex items-center justify-center text-3xl ${statusInfo.color}`}>
              {statusInfo.icon}
            </div>
          </div>

          {/* Status Text */}
          <div className="text-center">
            <h2 className="text-2xl font-bold mb-2">{statusInfo.title}</h2>
            <p className="text-gray-400 max-w-md">{job.message}</p>
          </div>

          {/* Progress Bar */}
          <div className="w-full max-w-md">
            <div className="flex justify-between text-sm text-gray-500 mb-2">
              <span>Overall Progress</span>
              <span>{Math.round(job.progress * 100)}%</span>
            </div>
            <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-math-blue to-math-purple transition-all duration-500"
                style={{ width: `${Math.max(job.progress * 100, 2)}%` }}
              />
            </div>
          </div>

          {/* Stage Indicators with Labels */}
          <div className="flex gap-1 sm:gap-3">
            {stages.map((stage, i) => {
              const isActive = job.status === stage.key
              const isComplete = getStageIndex(job.status) > i
              
              return (
                <div key={stage.key} className="flex flex-col items-center gap-1">
                  <div 
                    className={`w-3 h-3 sm:w-4 sm:h-4 rounded-full transition-all ${
                      isActive 
                        ? 'bg-math-blue ring-2 ring-math-blue/50 ring-offset-2 ring-offset-gray-950' 
                        : isComplete 
                          ? 'bg-math-blue' 
                          : 'bg-gray-700'
                    }`}
                  />
                  <span className={`text-[10px] sm:text-xs ${
                    isActive ? 'text-math-blue font-medium' : isComplete ? 'text-gray-400' : 'text-gray-600'
                  }`}>
                    {stage.label}
                  </span>
                </div>
              )
            })}
          </div>
          
          {/* Helpful tip */}
          <p className="text-xs text-gray-600 text-center">
            This may take several minutes depending on video complexity.<br/>
            You can leave this page open and check back later.
          </p>
        </div>

        {/* Detailed Section Progress - Side Panel */}
        {detailedProgress && (
          <SectionProgressView 
            details={detailedProgress}
            onSectionClick={(section: SectionProgress) => setSelectedSection(section)}
          />
        )}

        {/* Section Script Modal */}
        <SectionScriptModal 
          section={selectedSection}
          jobId={jobId}
          onClose={() => setSelectedSection(null)}
        />
      </div>
    )
  }

  // Failed View
  if (job.status === 'failed') {
    // Handle resume
    const handleResume = async () => {
      if (!jobId) return
      
      setIsResuming(true)
      try {
        // We need the original generation params - for now, navigate to a resume flow
        // or store them in the job data. For simplicity, we'll pass via URL
        const analysis = JSON.parse(sessionStorage.getItem('analysis') || 'null')
        const selectedTopics = JSON.parse(sessionStorage.getItem('selectedTopics') || '[]')
        
        if (!analysis || selectedTopics.length === 0) {
          // If we don't have the original analysis, we can't resume properly
          // Show a message and offer to go to gallery
          toast.error('Original generation data not found. Please start a new generation from the Gallery.')
          return
        }
        
        // Store the resume job ID and navigate to generation page
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
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <XCircle className="w-16 h-16 text-red-500" />
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">Generation Failed</h2>
          <p className="text-gray-400">{job.message}</p>
        </div>
        
        {/* Resume Info - show progress if available */}
        {resumeInfo && resumeInfo.can_resume && (
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 text-center max-w-md">
            <p className="text-sm text-gray-300 mb-2">
              <span className="text-math-blue font-medium">Progress saved!</span> You can resume from where it stopped.
            </p>
            <div className="text-xs text-gray-500 space-y-1">
              <p>✓ Script generated ({resumeInfo.total_sections} sections)</p>
              <p>✓ Completed {resumeInfo.completed_sections}/{resumeInfo.total_sections} sections</p>
              <p>○ {resumeInfo.total_sections - resumeInfo.completed_sections} sections remaining</p>
            </div>
          </div>
        )}
        
        <div className="flex gap-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 px-6 py-3 bg-gray-800 text-white rounded-lg 
                       hover:bg-gray-700 transition-colors"
          >
            <Home className="w-5 h-5" />
            Go Home
          </button>
          
          {resumeInfo?.can_resume ? (
            <button
              onClick={handleResume}
              disabled={isResuming}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-math-green to-teal-500 
                         text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {isResuming ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <RotateCcw className="w-5 h-5" />
              )}
              Resume ({resumeInfo.total_sections - resumeInfo.completed_sections} sections left)
            </button>
          ) : (
            <button
              onClick={() => window.location.reload()}
              className="flex items-center gap-2 px-6 py-3 bg-math-blue text-white rounded-lg 
                         hover:bg-math-blue/80 transition-colors"
            >
              <RefreshCw className="w-5 h-5" />
              Try Again
            </button>
          )}
        </div>
      </div>
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
            
            {/* Original Language */}
            {translations && (
              <p className="text-sm text-gray-500 mb-3">
                Original: {AVAILABLE_LANGUAGES.find(l => l.code === translations.original_language)?.name || translations.original_language}
              </p>
            )}
            
            {/* Translation List */}
            <div className="space-y-2">
              {translations?.translations.map(t => (
                <div 
                  key={t.language}
                  className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-gray-400" />
                    <span>{AVAILABLE_LANGUAGES.find(l => l.code === t.language)?.name || t.language}</span>
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
          
          {/* High Quality Compile Section */}
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
      
      {/* Translation Modal */}
      {showTranslationModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-xl p-6 max-w-md w-full mx-4 border border-gray-800">
            <h3 className="text-xl font-semibold mb-4">Add Translation</h3>
            <p className="text-gray-400 text-sm mb-4">
              Select a language to translate the video into. The narration will be translated and 
              new audio will be generated.
            </p>
            
            {/* Language Selection */}
            <label className="block text-sm font-medium text-gray-300 mb-2">Target Language</label>
            <div className="space-y-2 max-h-40 overflow-y-auto mb-4">
              {AVAILABLE_LANGUAGES
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
            
            {/* Voice Selection */}
            <label className="block text-sm font-medium text-gray-300 mb-2">Voice</label>
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="w-full p-3 rounded-lg bg-gray-800 border border-gray-700 text-white mb-4
                         focus:outline-none focus:border-math-purple"
            >
              {MULTILINGUAL_VOICES.map(voice => (
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
  // Use download_url from backend if available, otherwise construct it
  const videoUrl = video.download_url 
    ? (video.download_url.startsWith('http') ? video.download_url : `${API_BASE}${video.download_url}`)
    : getVideoUrl(video.video_id)

  console.log('VideoPlayer rendering with URL:', videoUrl)

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
      {/* Video */}
      <div className="aspect-video bg-black relative">
        <video
          src={videoUrl}
          className="w-full h-full"
          controls
          onError={(e) => console.error('Video load error:', e)}
        />
      </div>

      {/* Info */}
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

        {/* Chapters */}
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

function getStatusInfo(status?: string) {
  switch (status) {
    case 'pending':
      return { title: 'Starting Up', icon: '⏳', color: 'text-gray-400' }
    case 'analyzing':
      return { title: 'Analyzing Content', icon: '🔍', color: 'text-math-blue' }
    case 'generating_script':
      return { title: 'Writing Script', icon: '✍️', color: 'text-math-purple' }
    case 'creating_animations':
      return { title: 'Creating Sections', icon: '🎬', color: 'text-math-green' }  // Audio + Animation together
    case 'synthesizing_audio':
      return { title: 'Creating Sections', icon: '�', color: 'text-math-green' }  // Treat same as animations
    case 'composing_video':
      return { title: 'Composing Video', icon: '🎥', color: 'text-math-blue' }
    case 'completed':
      return { title: 'Complete!', icon: '✅', color: 'text-green-500' }
    case 'failed':
      return { title: 'Failed', icon: '❌', color: 'text-red-500' }
    default:
      return { title: 'Processing', icon: '⚡', color: 'text-math-blue' }
  }
}

function getStageIndex(status?: string): number {
  // Map synthesizing_audio to creating_animations since they happen together
  const mappedStatus = status === 'synthesizing_audio' ? 'creating_animations' : status
  const stages = ['pending', 'analyzing', 'generating_script', 'creating_animations', 'composing_video']
  return stages.indexOf(mappedStatus || '')
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
