import { Code, Volume2, Video } from 'lucide-react'
import { SectionProgress } from '../../../../types/job.types'
import { formatDuration } from '../../../../utils/format.utils'
import { getStatusConfig } from './utils'

interface SectionItemProps {
  section: SectionProgress
  isCurrent: boolean
  onClick: () => void
}

export function SectionItem({ section, isCurrent, onClick }: SectionItemProps) {
  const statusConfig = getStatusConfig(section.status)

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 p-2 rounded-lg text-left transition-all hover:bg-gray-800/80 ${
        isCurrent ? 'bg-gray-800 ring-1 ring-math-blue/50' : 'bg-transparent'
      }`}
    >
      {/* Status Icon */}
      <div className={`flex-shrink-0 ${statusConfig.color}`}>
        {statusConfig.icon}
      </div>

      {/* Section Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-500 font-mono">#{section.index + 1}</span>
          <span className="text-xs font-medium truncate">{section.title}</span>
        </div>
        
        {/* Status & indicators */}
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={`text-[10px] ${statusConfig.textColor}`}>
            {statusConfig.label}
          </span>
          
          <div className="flex items-center gap-1 ml-auto">
            {section.has_code && (
              <span title="Code generated">
                <Code className="w-2.5 h-2.5 text-green-500" />
              </span>
            )}
            {section.has_audio && (
              <span title="Audio generated">
                <Volume2 className="w-2.5 h-2.5 text-blue-500" />
              </span>
            )}
            {section.has_video && (
              <span title="Video complete">
                <Video className="w-2.5 h-2.5 text-math-green" />
              </span>
            )}
            {section.fix_attempts > 0 && (
              <span title={`${section.fix_attempts} fix attempts`} className="text-[9px] text-math-orange">
                ⚠{section.fix_attempts}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Duration */}
      {section.duration_seconds && section.duration_seconds > 0 && (
        <div className="text-[10px] text-gray-500 flex-shrink-0 font-mono">
          {formatDuration(section.duration_seconds)}
        </div>
      )}
    </button>
  )
}
