import React from 'react'
import { Home, RotateCcw, XCircle, Loader2 } from 'lucide-react'
import { JobResponse, ResumeInfo } from '../../../types/job.types'

interface ResultsPageFailedProps {
  job: JobResponse
  resumeInfo: ResumeInfo | null
  isResuming: boolean
  handleResume: () => void
  onGoHome: () => void
  onRetry: () => void
}

export const ResultsPageFailed: React.FC<ResultsPageFailedProps> = ({
  job, resumeInfo, isResuming, handleResume, onGoHome, onRetry
}) => (
  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
    <XCircle className="w-16 h-16 text-red-500" />
    <div className="text-center">
      <h2 className="text-2xl font-bold mb-2">Generation Failed</h2>
      <p className="text-gray-400">{job.message}</p>
    </div>
    
    {resumeInfo && resumeInfo.can_resume && (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 text-center max-w-md">
        <p className="text-sm text-gray-300 mb-2">
          <span className="text-math-blue font-medium">Progress saved!</span> You can resume from where it stopped.
        </p>
        <div className="text-xs text-gray-500 space-y-1">
          <p>✓ Script generated ({resumeInfo.total_sections} sections)</p>
          <p>✓ Completed {resumeInfo.completed_sections}/{resumeInfo.total_sections} sections</p>
          <p>○ {resumeInfo.total_sections - resumeInfo.completed_sections} sections remaining</p>
        </div>
      </div>
    )}
    
    <div className="flex gap-4">
      <button
        onClick={onGoHome}
        className="flex items-center gap-2 px-6 py-3 bg-gray-800 text-white rounded-lg 
                    hover:bg-gray-700 transition-colors"
      >
        <Home className="w-5 h-5" />
        Go Home
      </button>
      
      {resumeInfo?.can_resume ? (
        <button
          onClick={handleResume}
          disabled={isResuming}
          className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-math-green to-teal-500 
                      text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isResuming ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <RotateCcw className="w-5 h-5" />
          )}
          Resume ({resumeInfo.total_sections - resumeInfo.completed_sections} sections left)
        </button>
      ) : (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-6 py-3 bg-math-blue text-white rounded-lg 
                      hover:bg-math-blue/80 transition-colors"
        >
          <RefreshCw className="w-5 h-5" />
          Try Again
        </button>
      )}
    </div>
  </div>
)

import { RefreshCw } from 'lucide-react'
