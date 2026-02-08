import { useState, useEffect } from 'react'
import { 
  ChevronLeft, 
  ChevronRight, 
  FileText, 
  Loader2 
} from 'lucide-react'
import { SectionProgress, DetailedProgress } from '../../../../types/job.types'
import { SectionItem } from './SectionItem'

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
