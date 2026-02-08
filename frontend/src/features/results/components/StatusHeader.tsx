import React from 'react'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'
import { JobResponse } from '../../../types/job.types'

interface StatusHeaderProps {
  job: JobResponse | null
  error: string | null
}

export const StatusHeader: React.FC<StatusHeaderProps> = ({ job, error }) => {
  if (error) {
    return (
      <div className="flex items-center gap-4 p-4 bg-red-500/10 border border-red-500/50 rounded-xl">
        <XCircle className="w-8 h-8 text-red-500" />
        <div>
          <h2 className="text-xl font-bold">Error</h2>
          <p className="text-red-400">{error}</p>
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="flex items-center gap-4 p-4 bg-gray-900/50 border border-gray-800 rounded-xl animate-pulse">
        <Loader2 className="w-8 h-8 text-math-blue animate-spin" />
        <div>
          <h2 className="text-xl font-bold">Initializing...</h2>
          <p className="text-gray-400">Please wait while we fetch the job status.</p>
        </div>
      </div>
    )
  }

  const isCompleted = job.status === 'completed'
  const isFailed = job.status === 'failed'

  return (
    <div className={`flex items-center gap-4 p-4 rounded-xl border ${
      isCompleted ? 'bg-math-green/10 border-math-green/50' :
      isFailed ? 'bg-red-500/10 border-red-500/50' :
      'bg-math-blue/10 border-math-blue/50'
    }`}>
      {isCompleted ? <CheckCircle className="w-8 h-8 text-math-green" /> :
       isFailed ? <XCircle className="w-8 h-8 text-red-500" /> :
       <Loader2 className="w-8 h-8 text-math-blue animate-spin" />}
      
      <div>
        <h2 className="text-xl font-bold capitalize">
          {job.status.replace('_', ' ')}
        </h2>
        <p className="text-gray-400">{job.message}</p>
      </div>
    </div>
  )
}
