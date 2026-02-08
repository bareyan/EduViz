import { Sparkles, Brain, FileText, Palette, Box, CheckCircle, XCircle } from 'lucide-react'

export const getStatusInfo = (status: string | undefined) => {
  switch (status) {
    case 'pending':
      return { icon: <Sparkles />, color: 'text-yellow-400', title: 'Preparing...' }
    case 'analyzing':
      return { icon: <Brain />, color: 'text-math-blue', title: 'Analyzing...' }
    case 'generating_script':
      return { icon: <FileText />, color: 'text-math-orange', title: 'Writing Script...' }
    case 'creating_animations':
      return { icon: <Palette />, color: 'text-math-green', title: 'Creating Sections...' }
    case 'composing_video':
      return { icon: <Box />, color: 'text-math-purple', title: 'Composing Video...' }
    case 'completed':
      return { icon: <CheckCircle />, color: 'text-math-green', title: 'Completed!' }
    case 'failed':
      return { icon: <XCircle />, color: 'text-red-500', title: 'Failed' }
    default:
      return { icon: <Sparkles />, color: 'text-gray-400', title: 'Processing...' }
  }
}

export const stages = [
  { key: 'pending', label: 'Starting' },
  { key: 'analyzing', label: 'Analyzing' },
  { key: 'generating_script', label: 'Script' },
  { key: 'creating_animations', label: 'Animations' },
  { key: 'synthesizing_audio', label: 'Audio' },
  { key: 'composing_video', label: 'Composing' }
]

export const getStageIndex = (status: string | undefined) => {
  if (!status) return -1
  if (status === 'completed') return stages.length
  return stages.findIndex(s => s.key === status)
}
