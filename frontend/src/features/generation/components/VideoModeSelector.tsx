import React from 'react'
import { Clock, Zap } from 'lucide-react'

interface VideoModeSelectorProps {
  videoMode: 'comprehensive' | 'overview'
  setVideoMode: (mode: 'comprehensive' | 'overview') => void
}

export const VideoModeSelector: React.FC<VideoModeSelectorProps> = ({ videoMode, setVideoMode }) => (
  <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
    <div className="flex items-center gap-3 mb-4">
      <div className="p-2 bg-math-blue/20 rounded-lg">
        <Clock className="w-5 h-5 text-math-blue" />
      </div>
      <h2 className="text-lg font-semibold">Video Mode</h2>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <button
        onClick={() => setVideoMode('comprehensive')}
        className={`
          p-4 rounded-lg text-left transition-all
          ${videoMode === 'comprehensive' 
            ? 'bg-math-blue/20 border-math-blue border-2' 
            : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
          }
        `}
      >
        <div className="flex items-center gap-2 mb-2">
          <Clock className="w-5 h-5" />
          <p className="font-semibold">Comprehensive</p>
        </div>
        <p className="text-sm text-gray-400">
          Full detailed coverage with all proofs, examples, and explanations. 
          Longer videos (~15-45 min).
        </p>
      </button>
      <button
        onClick={() => setVideoMode('overview')}
        className={`
          p-4 rounded-lg text-left transition-all
          ${videoMode === 'overview' 
            ? 'bg-math-orange/20 border-math-orange border-2' 
            : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
          }
        `}
      >
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-5 h-5" />
          <p className="font-semibold">Quick Overview</p>
        </div>
        <p className="text-sm text-gray-400">
          Fast summary covering key concepts and main ideas.
          Shorter videos (~3-7 min).
        </p>
      </button>
    </div>
  </div>
)
