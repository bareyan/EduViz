import { Play } from 'lucide-react'
import { GeneratedVideo } from '../../../types/job.types'
import { formatDuration } from '../../../utils/format.utils'

interface VideoCardProps {
  video: GeneratedVideo;
  isSelected: boolean;
  onSelect: () => void;
}

export function VideoCard({ 
  video, 
  isSelected, 
  onSelect 
}: VideoCardProps) {
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
  );
}
