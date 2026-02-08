import React from 'react'
import { JobResponse, DetailedProgress, SectionProgress } from '../../../types/job.types'
import { SectionProgressView, SectionScriptModal } from '../../../components/SectionProgressView'
import { stages, getStageIndex } from '../results.utils'

interface ResultsPageInProgressProps {
  job: JobResponse
  statusInfo: { icon: React.ReactNode; color: string; title: string }
  detailedProgress: DetailedProgress | null
  selectedSection: SectionProgress | null
  setSelectedSection: (section: SectionProgress | null) => void
  jobId: string | undefined
}

export const ResultsPageInProgress: React.FC<ResultsPageInProgressProps> = ({
  job, statusInfo, detailedProgress, selectedSection, setSelectedSection, jobId
}) => {
  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
        <div className="relative">
          <div className="w-32 h-32 rounded-full border-4 border-math-blue/30 flex items-center justify-center">
            <div className="w-24 h-24 rounded-full border-4 border-t-math-blue border-r-transparent border-b-transparent border-l-transparent animate-spin" />
          </div>
          <div className={`absolute inset-0 flex items-center justify-center text-3xl ${statusInfo.color}`}>
            {statusInfo.icon}
          </div>
        </div>

        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">{statusInfo.title}</h2>
          <p className="text-gray-400 max-w-md">{job.message}</p>
        </div>

        <div className="w-full max-w-md">
          <div className="flex justify-between text-sm text-gray-500 mb-2">
            <span>Overall Progress</span>
            <span>{Math.round(job.progress * 100)}%</span>
          </div>
          <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-math-blue to-math-purple transition-all duration-500"
              style={{ width: `${Math.max(job.progress * 100, 2)}%` }}
            />
          </div>
        </div>

        <div className="flex gap-1 sm:gap-3">
          {stages.map((stage, i) => {
            const isActive = job.status === stage.key
            const isComplete = getStageIndex(job.status) > i
            
            return (
              <div key={stage.key} className="flex flex-col items-center gap-1">
                <div 
                  className={`w-3 h-3 sm:w-4 sm:h-4 rounded-full transition-all ${
                    isActive 
                      ? 'bg-math-blue ring-2 ring-math-blue/50 ring-offset-2 ring-offset-gray-950' 
                      : isComplete 
                        ? 'bg-math-blue' 
                        : 'bg-gray-700'
                  }`}
                />
                <span className={`text-[10px] sm:text-xs ${
                  isActive ? 'text-math-blue font-medium' : isComplete ? 'text-gray-400' : 'text-gray-600'
                }`}>
                  {stage.label}
                </span>
              </div>
            )
          })}
        </div>
        
        <p className="text-xs text-gray-600 text-center">
          This may take several minutes depending on video complexity.<br/>
          You can leave this page open and check back later.
        </p>
      </div>

      {detailedProgress && (
        <SectionProgressView 
          details={detailedProgress}
          onSectionClick={(section: SectionProgress) => setSelectedSection(section)}
        />
      )}

      <SectionScriptModal 
        section={selectedSection}
        jobId={jobId}
        onClose={() => setSelectedSection(null)}
      />
    </div>
  )
}
