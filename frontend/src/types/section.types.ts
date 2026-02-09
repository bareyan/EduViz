export interface SectionProgress {
  index: number
  id: string
  title: string
  status: 'waiting' | 'generating_script' | 'script_generated' | 'generating_manim' | 'fixing_manim' | 'generating_audio' | 'generating_video' | 'fixing_error' | 'completed' | 'failed'
  duration_seconds?: number
  narration_preview?: string
  has_video: boolean
  has_audio: boolean
  has_code: boolean
  error?: string
  fix_attempts: number
  qc_iterations: number
}
