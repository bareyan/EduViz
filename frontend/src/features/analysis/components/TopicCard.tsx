import { Check } from 'lucide-react'
import { TopicSuggestion } from '../../../types/analysis.types'

interface TopicCardProps {
  topic: TopicSuggestion
  isSelected: boolean
  onToggle: () => void
}

export function TopicCard({ 
  topic, 
  isSelected, 
  onToggle 
}: TopicCardProps) {
  const complexityColors: Record<string, string> = {
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
            <span className={`px-2 py-0.5 rounded-full text-xs ${complexityColors[topic.complexity] || 'bg-gray-500/20 text-gray-400'}`}>
              {topic.complexity}
            </span>
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
