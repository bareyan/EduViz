import { Download } from 'lucide-react'
import toast from 'react-hot-toast'
import { GeneratedVideo } from '../../../types/job.types'
import { generationService } from '../../../services/generation.service'
import { API_BASE } from '../../../config/api.config'
import { formatDuration } from '../../../utils/format.utils'

interface VideoPlayerProps {
  video: GeneratedVideo;
}

export function VideoPlayer({ video }: VideoPlayerProps) {
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
