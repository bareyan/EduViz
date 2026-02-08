import { useState, useEffect, useRef } from 'react'
import { jobService } from '../services/job.service'
import { JobResponse, DetailedProgress } from '../types/job.types'

export function useJobProgress(jobId: string | undefined, pollInterval = 3000) {
  const [job, setJob] = useState<JobResponse | null>(null)
  const [detailedProgress, setDetailedProgress] = useState<DetailedProgress | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchStatus = async () => {
    if (!jobId) return

    try {
      const [status, details] = await Promise.all([
        jobService.getJobStatus(jobId),
        jobService.getJobDetails(jobId)
      ])

      setJob(status)
      setDetailedProgress(details)
      setError(null)

      if (status.status === 'completed' || status.status === 'failed') {
        if (pollTimerRef.current) clearInterval(pollTimerRef.current)
      }
    } catch (err) {
      console.error('Failed to fetch job status:', err)
      setError('Failed to fetch job status')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!jobId) return

    fetchStatus()
    pollTimerRef.current = setInterval(fetchStatus, pollInterval)

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [jobId, pollInterval])

  return { job, detailedProgress, isLoading, error, refresh: fetchStatus }
}
