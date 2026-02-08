import { useParams, useNavigate } from 'react-router-dom'
import { BookOpen, Calculator, Clock, ChevronRight, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { useAnalysis } from '../hooks/useAnalysis'
import { StatCard } from '../features/analysis/components/StatCard'
import { TopicCard } from '../features/analysis/components/TopicCard'
import { AnalysisLoading } from '../features/analysis/components/AnalysisLoading'

export default function AnalysisPage() {
  const { fileId } = useParams<{ fileId: string }>()
  const navigate = useNavigate()
  
  const { analysis, selectedTopics, isLoading, error, toggleTopic, saveToStorage } = useAnalysis(fileId)

  const handleContinue = () => {
    if (selectedTopics.length === 0) {
      toast.error('Please select at least one topic')
      return
    }
    
    saveToStorage()
    navigate(`/generate/${analysis?.analysis_id}`)
  }

  if (isLoading) {
    return <AnalysisLoading />
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <AlertCircle className="w-16 h-16 text-red-500" />
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">Analysis Failed</h2>
          <p className="text-gray-400">{error}</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="px-6 py-3 bg-math-blue text-white rounded-lg hover:bg-math-blue/80 transition-colors"
        >
          Try Again
        </button>
      </div>
    )
  }

  if (!analysis) return null

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-4">Analysis Complete</h1>
        <p className="text-gray-400">{analysis.summary}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          icon={<BookOpen className="w-5 h-5" />}
          label="Pages"
          value={analysis.total_content_pages.toString()}
        />
        <StatCard
          icon={<Calculator className="w-5 h-5" />}
          label="Math Elements"
          value={analysis.detected_math_elements.toString()}
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="Est. Videos"
          value={analysis.estimated_total_videos.toString()}
        />
      </div>

      {/* Topic Selection */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Select Topics to Generate</h2>
        <p className="text-sm text-gray-500">
          Choose which topics you want to turn into videos. Each video will be max 20 minutes.
        </p>

        <div className="space-y-3">
          {analysis.suggested_topics.map(topic => (
            <TopicCard
              key={topic.index}
              topic={topic}
              isSelected={selectedTopics.includes(topic.index)}
              onToggle={() => toggleTopic(topic.index)}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between p-4 bg-gray-900/50 rounded-xl border border-gray-800">
        <div>
          <p className="text-sm text-gray-500">Selected: {selectedTopics.length} topics</p>
        </div>
        <button
          onClick={handleContinue}
          disabled={selectedTopics.length === 0}
          className="flex items-center gap-2 px-6 py-3 bg-math-blue text-white rounded-lg 
                     hover:bg-math-blue/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Continue
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}
