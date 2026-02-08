import { Loader2 } from 'lucide-react'

export function AnalysisLoading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
      <div className="relative">
        <Loader2 className="w-16 h-16 text-math-blue animate-spin" />
        <div className="absolute inset-0 bg-math-blue/20 blur-xl pulse-ring" />
      </div>
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-2">Analyzing Your Material</h2>
        <p className="text-gray-400">Detecting equations, theorems, and key concepts...</p>
      </div>
    </div>
  )
}
