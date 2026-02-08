import React from 'react'
import { AnalysisResult } from '../../../types/analysis.types'

interface SummaryCardProps {
  selectedTopics: number[]
  analysis: AnalysisResult
}

export const SummaryCard: React.FC<SummaryCardProps> = ({ selectedTopics, analysis }) => {
  const selectedTopicData = analysis.suggested_topics.filter(t => selectedTopics.includes(t.index))

  return (
    <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
      <h2 className="text-lg font-semibold mb-4">Generation Summary</h2>
      <div className="grid grid-cols-1">
        <div>
          <p className="text-sm text-gray-500">Topics Selected</p>
          <p className="text-xl font-bold">{selectedTopics.length}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {selectedTopicData.map(topic => (
          <span 
            key={topic.index}
            className="px-3 py-1 bg-math-blue/20 text-math-blue rounded-full text-sm"
          >
            {topic.title}
          </span>
        ))}
      </div>
    </div>
  )
}
