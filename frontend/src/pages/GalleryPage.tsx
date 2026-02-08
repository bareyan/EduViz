import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Loader2,
  Trash2,
  RefreshCw,
  Video,
  Home
} from 'lucide-react'
import toast from 'react-hot-toast'
import { GalleryJob } from '../types/job.types'
import { jobService } from '../services/job.service'
import { JobCard } from '../features/gallery/components/JobCard'

export default function GalleryPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<GalleryJob[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed' | 'pending'>('all')

  const loadJobs = async () => {
    setLoading(true)
    try {
      const allJobs = await jobService.listAllJobs()
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
      await jobService.deleteJob(jobId)
      toast.success('Job deleted')
      loadJobs()
    } catch (error) {
      toast.error('Failed to delete job')
    }
  }

  const handleDeleteAllFailed = async () => {
    if (!confirm('Delete all failed jobs and their files?')) return

    try {
      const result = await jobService.deleteFailedJobs()
      toast.success(`Deleted ${result.deleted_count} failed jobs`)
      loadJobs()
    } catch (error) {
      toast.error('Failed to delete failed jobs')
    }
  }

  const handleEditJob = async (job: GalleryJob) => {
    const newTitle = window.prompt("Rename Video:", job.title || "")
    if (newTitle && newTitle !== job.title) {
      try {
        await jobService.updateJob(job.id, { title: newTitle })
        toast.success("Video renamed")
        loadJobs()
      } catch (error) {
        console.error(error)
        toast.error("Failed to rename video")
      }
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
            className={`px-4 py-2 rounded-t-lg transition-colors ${filter === tab.key
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
              onEdit={() => handleEditJob(job)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
