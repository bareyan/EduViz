import { 
  CheckCircle, 
  Loader2, 
  Wrench, 
  Clock, 
  AlertCircle 
} from 'lucide-react'
import { SectionProgress } from '../../../../types/job.types'

export function getStatusConfig(status: SectionProgress['status']) {
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
    case 'script_generated':
      return {
        icon: <CheckCircle className="w-3.5 h-3.5" />,
        color: 'text-emerald-400',
        textColor: 'text-emerald-400',
        label: 'Script generated'
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
