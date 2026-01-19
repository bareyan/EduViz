import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  Download, 
  Play, 
  Home,
  RefreshCw
} from 'lucide-react'
import toast from 'react-hot-toast'
import { getJobStatus, JobResponse, GeneratedVideo, getVideoUrl, API_BASE } from '../api'

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  
  const [job, setJob] = useState<JobResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedVideo, setSelectedVideo] = useState<GeneratedVideo | null>(null)

  useEffect(() => {
    if (!jobId) return

    let isMounted = true
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const pollStatus = async () => {
      try {
        const status = await getJobStatus(jobId)
        
        if (!isMounted) return
        
        // Force update by creating a new object reference
        setJob({ ...status })

        if (status.status === 'completed' && status.result && status.result.length > 0) {
          setSelectedVideo(status.result[0])
        }

        // Continue polling if not completed or failed
        if (status.status !== 'completed' && status.status !== 'failed') {
          timeoutId = setTimeout(pollStatus, 1500)  // Slightly faster polling
        }
      } catch (err) {
        console.error('Failed to get job status:', err)
        if (isMounted) {
          setError('Failed to get job status')
        }
      }
    }

    pollStatus()

    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [jobId])  // Only depend on jobId, not job.status

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
      </div>
    )
  }

  // Failed View
  if (job.status === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <XCircle className="w-16 h-16 text-red-500" />
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">Generation Failed</h2>
          <p className="text-gray-400">{job.message}</p>
        </div>
        <div className="flex gap-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 px-6 py-3 bg-gray-800 text-white rounded-lg 
                       hover:bg-gray-700 transition-colors"
          >
            <Home className="w-5 h-5" />
            Go Home
          </button>
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 px-6 py-3 bg-math-blue text-white rounded-lg 
                       hover:bg-math-blue/80 transition-colors"
          >
            <RefreshCw className="w-5 h-5" />
            Try Again
          </button>
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
        </div>
      </div>
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
