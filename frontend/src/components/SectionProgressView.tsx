import { useState, useEffect } from 'react'
import { 
  ChevronLeft, 
  ChevronRight, 
  Clock, 
  CheckCircle, 
  Loader2, 
  AlertCircle,
  FileText,
  Video,
  Volume2,
  Code,
  X,
  Wrench,
  Eye,
  Play
} from 'lucide-react'
import { SectionProgress, DetailedProgress, SectionDetails } from '../types/job.types'
import { API_BASE } from '../config/api.config'
import { jobService } from '../services/job.service'

interface SectionProgressViewProps {
  details: DetailedProgress
  onSectionClick?: (section: SectionProgress) => void
}

export function SectionProgressView({ details, onSectionClick }: SectionProgressViewProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  // Debug log
  useEffect(() => {
    console.log('SectionProgressView received details:', {
      script_ready: details.script_ready,
      script_title: details.script_title,
      total_sections: details.total_sections,
      completed_sections: details.completed_sections,
      sections_count: details.sections?.length || 0,
      has_sections_array: Array.isArray(details.sections),
      current_stage: details.current_stage,
      raw_sections: details.sections
    })
  }, [details])

  // Only hide if we're in very early stages (analyzing stage AND no sections info yet)
  const shouldShow = details.script_ready || details.total_sections > 0 || details.current_stage === 'sections'
  
  if (!shouldShow) {
    return null
  }

  // Calculate stage description for current stage
  const getStageDescription = () => {
    switch (details.current_stage) {
      case 'analyzing':
        return 'Analyzing document...'
      case 'script':
        return 'Generating script...'
      case 'sections':
        return 'Processing sections...'
      case 'combining':
        return 'Combining final video...'
      case 'completed':
        return 'Generation complete!'
      case 'failed':
        return 'Generation failed'
      default:
        return details.message || 'Processing...'
    }
  }

  return (
    <div 
      className={`fixed right-0 top-16 h-[calc(100vh-4rem)] bg-gray-900 border-l border-gray-800 transition-all duration-300 z-40 flex ${isExpanded ? 'w-96' : 'w-0'}`}
    >
      {/* Toggle Button - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="absolute -left-10 top-1/2 -translate-y-1/2 p-2 bg-gray-800 border border-gray-700 rounded-l-lg hover:bg-gray-700 transition-colors z-50"
        title={isExpanded ? 'Hide section details' : 'Show section details'}
      >
        {isExpanded ? (
          <ChevronRight className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronLeft className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {/* Panel Content */}
      {isExpanded && (
        <div className="flex flex-col w-full h-full overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-gray-800 flex-shrink-0">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-math-purple" />
              <h3 className="font-medium text-sm truncate">
                {details.script_title || (details.total_sections > 0 ? 'Educational Video' : 'Processing...')}
              </h3>
            </div>
            
            {/* Progress bar */}
            {details.total_sections > 0 && (
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-math-blue transition-all duration-300"
                    style={{ 
                      width: `${details.total_sections > 0 
                        ? (details.completed_sections / details.total_sections) * 100 
                        : 0}%` 
                    }}
                  />
                </div>
                <span className="text-xs text-gray-500 tabular-nums">
                  {details.completed_sections}/{details.total_sections}
                </span>
              </div>
            )}

            {/* Current stage */}
            <div className="text-xs text-gray-400">
              {getStageDescription()}
            </div>
          </div>

          {/* Section List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {Array.isArray(details.sections) && details.sections.length > 0 ? (
              details.sections.map((section) => (
                <SectionItem 
                  key={section.id} 
                  section={section}
                  isCurrent={details.current_section_index === section.index}
                  onClick={() => onSectionClick?.(section)}
                />
              ))
            ) : (
              <div className="text-center text-gray-500 text-xs py-8">
                {details.current_stage === 'script' ? (
                  <div>
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-math-blue" />
                    <p>Generating script...</p>
                  </div>
                ) : details.total_sections > 0 ? (
                  <div>
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-math-blue" />
                    <p>Loading {details.total_sections} sections...</p>
                  </div>
                ) : (
                  <p>No sections yet</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

interface SectionItemProps {
  section: SectionProgress
  isCurrent: boolean
  onClick: () => void
}

function SectionItem({ section, isCurrent, onClick }: SectionItemProps) {
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

function getStatusConfig(status: SectionProgress['status']) {
  switch (status) {
    case 'completed':
      return {
        icon: <CheckCircle className="w-3.5 h-3.5" />,
        color: 'text-math-green',
        textColor: 'text-math-green',
        label: 'Complete'
      }
    case 'generating_video':
      return {
        icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
        color: 'text-math-blue',
        textColor: 'text-math-blue',
        label: 'Rendering video...'
      }
    case 'generating_manim':
      return {
        icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
        color: 'text-math-purple',
        textColor: 'text-math-purple',
        label: 'Generating animation...'
      }
    case 'fixing_error':
      return {
        icon: <Wrench className="w-3.5 h-3.5 animate-pulse" />,
        color: 'text-math-orange',
        textColor: 'text-math-orange',
        label: 'Fixing error...'
      }
    case 'fixing_manim':
      return {
        icon: <Wrench className="w-3.5 h-3.5 animate-pulse" />,
        color: 'text-math-orange',
        textColor: 'text-math-orange',
        label: 'Fixing animation...'
      }
    case 'generating_audio':
      return {
        icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
        color: 'text-teal-400',
        textColor: 'text-teal-400',
        label: 'Generating audio...'
      }
    case 'generating_script':
      return {
        icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
        color: 'text-yellow-500',
        textColor: 'text-yellow-500',
        label: 'Writing script...'
      }
    case 'failed':
      return {
        icon: <AlertCircle className="w-3.5 h-3.5" />,
        color: 'text-red-500',
        textColor: 'text-red-500',
        label: 'Failed'
      }
    case 'waiting':
    default:
      return {
        icon: <Clock className="w-3.5 h-3.5" />,
        color: 'text-gray-500',
        textColor: 'text-gray-500',
        label: 'Waiting'
      }
  }
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  if (mins > 0) {
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  return `${secs}s`
}

// === Simple Markdown Renderer ===

function SimpleMarkdown({ content }: { content: string }) {
  const renderMarkdown = (text: string) => {
    const lines = text.split('\n')
    const elements: JSX.Element[] = []
    let i = 0
    let inCodeBlock = false
    let codeContent: string[] = []
    let inTable = false
    let tableRows: string[][] = []

    while (i < lines.length) {
      const line = lines[i]

      // Code block
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          elements.push(
            <pre key={i} className="bg-gray-800 p-3 rounded text-xs overflow-x-auto my-2 font-mono text-gray-300">
              {codeContent.join('\n')}
            </pre>
          )
          codeContent = []
          inCodeBlock = false
        } else {
          inCodeBlock = true
        }
        i++
        continue
      }

      if (inCodeBlock) {
        codeContent.push(line)
        i++
        continue
      }

      // Table
      if (line.startsWith('|')) {
        if (!inTable) {
          inTable = true
          tableRows = []
        }
        // Skip separator rows
        if (!line.match(/^\|[\s\-:|]+\|$/)) {
          const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim())
          tableRows.push(cells)
        }
        i++
        continue
      } else if (inTable) {
        elements.push(
          <div key={i} className="overflow-x-auto my-2">
            <table className="text-xs border-collapse w-full">
              <tbody>
                {tableRows.map((row, rowIdx) => (
                  <tr key={rowIdx} className={rowIdx === 0 ? 'bg-gray-800 font-medium' : 'border-t border-gray-700'}>
                    {row.map((cell, cellIdx) => (
                      <td key={cellIdx} className="px-2 py-1 text-gray-300">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        tableRows = []
        inTable = false
        continue
      }

      // Horizontal rule
      if (line.match(/^[-=]{3,}$/)) {
        elements.push(<hr key={i} className="border-gray-700 my-3" />)
        i++
        continue
      }

      // Headers
      if (line.startsWith('## ')) {
        elements.push(
          <h3 key={i} className="text-sm font-semibold text-math-purple mt-4 mb-2">
            {line.slice(3)}
          </h3>
        )
        i++
        continue
      }
      if (line.startsWith('### ')) {
        elements.push(
          <h4 key={i} className="text-xs font-medium text-gray-300 mt-3 mb-1">
            {line.slice(4)}
          </h4>
        )
        i++
        continue
      }

      // Warning/emphasis
      if (line.startsWith('⚠️') || line.startsWith('═')) {
        elements.push(
          <div key={i} className="text-xs text-yellow-500 font-medium my-2">
            {line}
          </div>
        )
        i++
        continue
      }

      // List items
      if (line.startsWith('- ')) {
        elements.push(
          <div key={i} className="text-xs text-gray-400 pl-3 my-0.5">
            • {line.slice(2)}
          </div>
        )
        i++
        continue
      }

      // Empty line
      if (line.trim() === '') {
        elements.push(<div key={i} className="h-2" />)
        i++
        continue
      }

      // Regular text
      elements.push(
        <p key={i} className="text-xs text-gray-400 my-1">
          {line}
        </p>
      )
      i++
    }

    // Flush remaining table
    if (inTable && tableRows.length > 0) {
      elements.push(
        <div key="final-table" className="overflow-x-auto my-2">
          <table className="text-xs border-collapse w-full">
            <tbody>
              {tableRows.map((row, rowIdx) => (
                <tr key={rowIdx} className={rowIdx === 0 ? 'bg-gray-800 font-medium' : 'border-t border-gray-700'}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} className="px-2 py-1 text-gray-300">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    return elements
  }

  return <div className="markdown-content">{renderMarkdown(content)}</div>
}

// === Section Script Modal ===

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
