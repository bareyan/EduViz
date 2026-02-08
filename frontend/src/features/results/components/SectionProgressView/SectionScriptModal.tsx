import { useState, useEffect } from 'react'
import { 
  X, 
  Volume2, 
  Eye, 
  Code, 
  Loader2, 
  Video, 
  Wrench, 
  Play 
} from 'lucide-react'
import { SectionProgress, SectionDetails } from '../../../../types/job.types'
import { formatDuration } from '../../../../utils/format.utils'
import { jobService } from '../../../../services/job.service'
import { API_BASE } from '../../../../config/api.config'
import { getStatusConfig } from './utils'
import { SimpleMarkdown } from './SimpleMarkdown'

interface SectionScriptModalProps {
  section: SectionProgress | null
  jobId?: string
  onClose: () => void
}

export function SectionScriptModal({ section, jobId, onClose }: SectionScriptModalProps) {
  const [details, setDetails] = useState<SectionDetails | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'audio' | 'visual' | 'code'>('audio')

  useEffect(() => {
    if (section && jobId) {
      setLoading(true)
      jobService.getSectionDetails(jobId, section.index)
        .then(data => {
          setDetails(data)
        })
        .catch(err => {
          console.error('Failed to load section details:', err)
        })
        .finally(() => setLoading(false))
    } else {
      setDetails(null)
    }
  }, [section, jobId])

  if (!section) return null

  const statusConfig = getStatusConfig(section.status)

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-xl border border-gray-800 max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className={statusConfig.color}>
              {statusConfig.icon}
            </div>
            <div>
              <h3 className="font-semibold text-sm">Section {section.index + 1}: {section.title}</h3>
              <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                <span className={statusConfig.textColor}>{statusConfig.label}</span>
                {section.duration_seconds && (
                  <>
                    <span>•</span>
                    <span>{formatDuration(section.duration_seconds)}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-2 border-b border-gray-800 bg-gray-900 flex-shrink-0">
          <button
            onClick={() => setActiveTab('audio')}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              activeTab === 'audio' 
                ? 'bg-math-blue/20 text-math-blue' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Volume2 className="w-4 h-4" />
              Audio Script
            </span>
          </button>
          <button
            onClick={() => setActiveTab('visual')}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              activeTab === 'visual' 
                ? 'bg-math-purple/20 text-math-purple' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Eye className="w-4 h-4" />
              Visual Script
            </span>
          </button>
          {(details?.code || section.has_code) && (
            <button
              onClick={() => setActiveTab('code')}
              className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                activeTab === 'code' 
                  ? 'bg-math-green/20 text-math-green' 
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              <span className="flex items-center gap-2">
                <Code className="w-4 h-4" />
                Manim Code
              </span>
            </button>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-math-blue" />
            </div>
          ) : (
            <>
              {/* Status Badges */}
              <div className="flex flex-wrap gap-2 mb-4">
                {section.has_code && (
                  <span className="px-2 py-1 bg-gray-800 rounded text-xs flex items-center gap-1">
                    <Code className="w-3 h-3" /> Code Ready
                  </span>
                )}
                {section.has_audio && (
                  <span className="px-2 py-1 bg-gray-800 rounded text-xs flex items-center gap-1">
                    <Volume2 className="w-3 h-3" /> Audio Ready
                  </span>
                )}
                {section.has_video && (
                  <span className="px-2 py-1 bg-math-green/20 text-math-green rounded text-xs flex items-center gap-1">
                    <Video className="w-3 h-3" /> Video Complete
                  </span>
                )}
                {section.fix_attempts > 0 && (
                  <span className="px-2 py-1 bg-math-orange/20 text-math-orange rounded text-xs flex items-center gap-1">
                    <Wrench className="w-3 h-3" /> {section.fix_attempts} fix attempts
                  </span>
                )}
              </div>

              {/* Tab Content */}
              {activeTab === 'audio' && (
                <div>
                  <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                    {details?.narration ? (
                      <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                        {details.narration}
                      </p>
                    ) : section.narration_preview ? (
                      <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                        {section.narration_preview}
                      </p>
                    ) : (
                      <p className="text-sm text-gray-500 italic">
                        Audio script not yet generated
                      </p>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'visual' && (
                <div className="bg-gray-800/30 rounded-lg border border-gray-700 p-4">
                  {details?.visual_description ? (
                    <SimpleMarkdown content={details.visual_description} />
                  ) : (
                    <p className="text-sm text-gray-500 italic">
                      Visual script not available
                    </p>
                  )}
                </div>
              )}

              {activeTab === 'code' && (
                <div>
                  <div className="p-4 bg-gray-900 rounded-lg border border-gray-700 font-mono text-xs overflow-x-auto">
                    {details?.code ? (
                      <pre className="text-gray-300 whitespace-pre">{details.code}</pre>
                    ) : (
                      <p className="text-gray-500 italic">Code not yet generated</p>
                    )}
                  </div>
                </div>
              )}

              {/* Video Preview */}
              {details?.video_url && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                    <Play className="w-4 h-4" /> Preview
                  </h4>
                  <video 
                    src={`${API_BASE}${details.video_url}`}
                    controls
                    className="w-full rounded-lg"
                  />
                </div>
              )}

              {/* Error Message */}
              {section.error && (
                <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <h4 className="text-sm font-medium text-red-400 mb-1">Error</h4>
                  <p className="text-sm text-red-300">{section.error}</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
