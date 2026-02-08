import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Loader2,
  CheckCircle,
  XCircle,
  Home,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { GeneratedVideo, SectionProgress } from '../types/job.types'

import { jobService } from '../services/job.service'
import { useJobProgress } from '../hooks/useJobProgress'

import { ResultsPageInProgress } from '../features/results/components/ResultsPageInProgress'
import { ResultsPageFailed } from '../features/results/components/ResultsPageFailed'
import { VideoPlayer } from '../features/results/components/VideoPlayer'
import { VideoCard } from '../features/results/components/VideoCard'

import { getStatusInfo } from '../features/results/results.utils'

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()

  const { job, detailedProgress, error } = useJobProgress(jobId)


  const [selectedVideo, setSelectedVideo] = useState<GeneratedVideo | null>(null)


  // Resume state
  const [resumeInfo, setResumeInfo] = useState<any | null>(null)
  const [isResuming, setIsResuming] = useState(false)



  // Section modal state
  const [selectedSection, setSelectedSection] = useState<SectionProgress | null>(null)



  useEffect(() => {
    if (job?.status === 'completed' && job.result && job.result.length > 0) {
      setSelectedVideo(job.result[0])
    }
    if (job?.status === 'failed' && jobId) {
      jobService.getResumeInfo(jobId).then(setResumeInfo).catch(console.error)
    }
  }, [job?.status, job?.result, jobId])

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
        </div>
      </div>
    </div>
  )
}
