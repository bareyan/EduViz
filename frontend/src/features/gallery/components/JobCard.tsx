import {
  Loader2,
  Play,
  Trash2,
  Clock,
  CheckCircle,
  XCircle,
  Edit
} from 'lucide-react'
import { GalleryJob } from '../../../types/job.types'
import { API_BASE } from '../../../config/api.config'
import { formatDuration } from '../../../utils/format.utils'

interface JobCardProps {
  job: GalleryJob
  onDelete: () => void
  onView: () => void
  onEdit: () => void
}

export function JobCard({
  job,
  onDelete,
  onView,
  onEdit
}: JobCardProps) {
  const isCompleted = job.status === 'completed'
  const isFailed = job.status === 'failed'
  const isPending = !isCompleted && !isFailed

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
            poster={job.thumbnail_url ? `${API_BASE}${job.thumbnail_url}` : undefined}
            preload="none"
            className="w-full h-full object-cover"
            muted
            onMouseEnter={(e) => {
              if (e.currentTarget.paused) {
                e.currentTarget.play().catch(() => { })
              }
            }}
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
