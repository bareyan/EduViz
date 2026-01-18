import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Loader2, 
  Play, 
  Trash2, 
  Clock, 
  CheckCircle,
  XCircle,
  RefreshCw,
  Edit,
  Video,
  Home
} from 'lucide-react'
import toast from 'react-hot-toast'
import { 
  listAllJobs, 
  deleteJob, 
  deleteFailedJobs, 
  GalleryJob,
  API_BASE
} from '../api'

export default function GalleryPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<GalleryJob[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed' | 'pending'>('all')

  const loadJobs = async () => {
    setLoading(true)
    try {
      const allJobs = await listAllJobs()
      // Sort by updated_at descending
      allJobs.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      setJobs(allJobs)
    } catch (error) {
      console.error('Failed to load jobs:', error)
      toast.error('Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadJobs()
  }, [])

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job?')) return
    
    try {
      await deleteJob(jobId)
      toast.success('Job deleted')
      loadJobs()
    } catch (error) {
      toast.error('Failed to delete job')
    }
  }

  const handleDeleteAllFailed = async () => {
    if (!confirm('Delete all failed jobs and their files?')) return
    
    try {
      const result = await deleteFailedJobs()
      toast.success(`Deleted ${result.deleted_count} failed jobs`)
      loadJobs()
    } catch (error) {
      toast.error('Failed to delete failed jobs')
    }
  }

  const filteredJobs = jobs.filter(job => {
    if (filter === 'all') return true
    if (filter === 'completed') return job.status === 'completed'
    if (filter === 'failed') return job.status === 'failed'
    if (filter === 'pending') return !['completed', 'failed'].includes(job.status)
    return true
  })

  const completedCount = jobs.filter(j => j.status === 'completed').length
  const failedCount = jobs.filter(j => j.status === 'failed').length
  const pendingCount = jobs.filter(j => !['completed', 'failed'].includes(j.status)).length

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <Loader2 className="w-16 h-16 text-math-blue animate-spin" />
        <p className="text-gray-400">Loading gallery...</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">Video Gallery</h1>
          <p className="text-gray-400">
            {jobs.length} total jobs • {completedCount} completed • {failedCount} failed
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={loadJobs}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-white rounded-lg 
                       hover:bg-gray-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          {failedCount > 0 && (
            <button
              onClick={handleDeleteAllFailed}
              className="flex items-center gap-2 px-4 py-2 bg-red-600/20 text-red-400 rounded-lg 
                         hover:bg-red-600/30 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Delete Failed ({failedCount})
            </button>
          )}
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 px-4 py-2 bg-math-blue text-white rounded-lg 
                       hover:bg-math-blue/80 transition-colors"
          >
            <Home className="w-4 h-4" />
            New Video
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-gray-800 pb-2">
        {[
          { key: 'all', label: `All (${jobs.length})` },
          { key: 'completed', label: `Completed (${completedCount})` },
          { key: 'failed', label: `Failed (${failedCount})` },
          { key: 'pending', label: `In Progress (${pendingCount})` },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key as any)}
            className={`px-4 py-2 rounded-t-lg transition-colors ${
              filter === tab.key
                ? 'bg-gray-800 text-white'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Jobs Grid */}
      {filteredJobs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-500">
          <Video className="w-16 h-16 mb-4 opacity-50" />
          <p>No videos found</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredJobs.map(job => (
            <JobCard 
              key={job.id} 
              job={job} 
              onDelete={() => handleDeleteJob(job.id)}
              onView={() => navigate(`/results/${job.id}`)}
              onEdit={() => navigate(`/edit/${job.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function JobCard({ 
  job, 
  onDelete, 
  onView,
  onEdit 
}: { 
  job: GalleryJob
  onDelete: () => void
  onView: () => void
  onEdit: () => void
}) {
  const isCompleted = job.status === 'completed'
  const isFailed = job.status === 'failed'
  const isPending = !isCompleted && !isFailed

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className={`
      rounded-xl border overflow-hidden transition-all
      ${isCompleted ? 'bg-gray-900/50 border-gray-800 hover:border-gray-700' : ''}
      ${isFailed ? 'bg-red-900/10 border-red-900/50' : ''}
      ${isPending ? 'bg-blue-900/10 border-blue-900/50' : ''}
    `}>
      {/* Thumbnail / Status */}
      <div className="aspect-video bg-gray-800 relative flex items-center justify-center">
        {isCompleted && job.video_url ? (
          <video 
            src={`${API_BASE}${job.video_url}`}
            className="w-full h-full object-cover"
            muted
            onMouseEnter={(e) => e.currentTarget.play()}
            onMouseLeave={(e) => {
              e.currentTarget.pause()
              e.currentTarget.currentTime = 0
            }}
          />
        ) : (
          <div className="flex flex-col items-center gap-2">
            {isCompleted && <CheckCircle className="w-12 h-12 text-green-500" />}
            {isFailed && <XCircle className="w-12 h-12 text-red-500" />}
            {isPending && <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />}
            <span className="text-sm text-gray-400 capitalize">{job.status}</span>
          </div>
        )}
        
        {/* Progress overlay for pending */}
        {isPending && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-700">
            <div 
              className="h-full bg-blue-500 transition-all"
              style={{ width: `${(job.progress || 0) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-4">
        <h3 className="font-medium truncate mb-1">
          {job.title || job.id.substring(0, 20)}
        </h3>
        
        <div className="flex items-center gap-3 text-sm text-gray-500 mb-3">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDate(job.updated_at)}
          </span>
          {job.total_duration && (
            <span>{formatDuration(job.total_duration)}</span>
          )}
          {job.sections_count && (
            <span>{job.sections_count} sections</span>
          )}
        </div>

        {isPending && (
          <p className="text-xs text-blue-400 mb-3 truncate">{job.message}</p>
        )}
        
        {isFailed && (
          <p className="text-xs text-red-400 mb-3 truncate">{job.message}</p>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {isCompleted && (
            <>
              <button
                onClick={onView}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 
                           bg-math-blue text-white rounded-lg hover:bg-math-blue/80 transition-colors"
              >
                <Play className="w-4 h-4" />
                Watch
              </button>
              <button
                onClick={onEdit}
                className="flex items-center justify-center gap-2 px-3 py-2 
                           bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
              >
                <Edit className="w-4 h-4" />
              </button>
            </>
          )}
          
          {isPending && (
            <button
              onClick={onView}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 
                         bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              View Progress
            </button>
          )}
          
          <button
            onClick={onDelete}
            className="flex items-center justify-center gap-2 px-3 py-2 
                       bg-red-600/20 text-red-400 rounded-lg hover:bg-red-600/30 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
