import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loader2, BookOpen, Calculator, Clock, ChevronRight, Check, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { analyzeFile, AnalysisResult, TopicSuggestion } from '../api'

export default function AnalysisPage() {
  const { fileId } = useParams<{ fileId: string }>()
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [selectedTopics, setSelectedTopics] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Prevent double-call in React StrictMode
  const hasAnalyzed = useRef(false)

  useEffect(() => {
    if (!fileId) return
    
    // Prevent double-analysis in StrictMode
    if (hasAnalyzed.current) return
    hasAnalyzed.current = true

    const runAnalysis = async () => {
      try {
        setIsLoading(true)
        const result = await analyzeFile(fileId)
        setAnalysis(result)
        // Select all topics by default
        setSelectedTopics(result.suggested_topics.map(t => t.index))
      } catch (err) {
        console.error('Analysis failed:', err)
        setError('Failed to analyze the file. Please try again.')
        toast.error('Analysis failed')
      } finally {
        setIsLoading(false)
      }
    }

    runAnalysis()
  }, [fileId])

  const toggleTopic = (index: number) => {
    setSelectedTopics(prev => 
      prev.includes(index) 
        ? prev.filter(i => i !== index)
        : [...prev, index]
    )
  }

  const handleContinue = () => {
    if (selectedTopics.length === 0) {
      toast.error('Please select at least one topic')
      return
    }
    
    // Store selection in session storage for the next page
    sessionStorage.setItem('selectedTopics', JSON.stringify(selectedTopics))
    sessionStorage.setItem('analysis', JSON.stringify(analysis))
    
    navigate(`/generate/${analysis?.analysis_id}`)
  }

  if (isLoading) {
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

  const totalDuration = selectedTopics.reduce((sum, idx) => {
    const topic = analysis.suggested_topics.find(t => t.index === idx)
    return sum + (topic?.estimated_duration || 0)
  }, 0)

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
          <p className="text-lg font-semibold">~{totalDuration} minutes total</p>
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

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="p-4 bg-gray-900/50 rounded-xl border border-gray-800 text-center">
      <div className="flex justify-center text-math-blue mb-2">{icon}</div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}

function TopicCard({ 
  topic, 
  isSelected, 
  onToggle 
}: { 
  topic: TopicSuggestion
  isSelected: boolean
  onToggle: () => void 
}) {
  const complexityColors = {
    beginner: 'bg-green-500/20 text-green-400',
    intermediate: 'bg-yellow-500/20 text-yellow-400',
    advanced: 'bg-red-500/20 text-red-400',
  }

  return (
    <div
      onClick={onToggle}
      className={`
        p-4 rounded-xl border cursor-pointer transition-all
        ${isSelected 
          ? 'bg-math-blue/10 border-math-blue' 
          : 'bg-gray-900/50 border-gray-800 hover:border-gray-700'
        }
      `}
    >
      <div className="flex items-start gap-4">
        <div className={`
          w-6 h-6 rounded-md border-2 flex items-center justify-center flex-shrink-0 mt-0.5
          ${isSelected ? 'bg-math-blue border-math-blue' : 'border-gray-600'}
        `}>
          {isSelected && <Check className="w-4 h-4 text-white" />}
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="font-semibold">{topic.title}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs ${complexityColors[topic.complexity]}`}>
              {topic.complexity}
            </span>
            <span className="text-sm text-gray-500">~{topic.estimated_duration} min</span>
          </div>
          <p className="text-sm text-gray-400 mb-2">{topic.description}</p>
          {topic.subtopics.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {topic.subtopics.map((subtopic, i) => (
                <span key={i} className="px-2 py-1 bg-gray-800 rounded text-xs text-gray-400">
                  {subtopic}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
