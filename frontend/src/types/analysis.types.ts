export interface UploadResponse {
  file_id: string
  filename: string
  size: number
  type: string
}

export interface TopicSuggestion {
  index: number
  title: string
  description: string
  estimated_duration: number
  complexity: 'beginner' | 'intermediate' | 'advanced'
  subtopics: string[]
}

export interface AnalysisResult {
  analysis_id: string
  file_id: string
  material_type: string
  total_content_pages: number
  detected_math_elements: number
  suggested_topics: TopicSuggestion[]
  estimated_total_videos: number
  summary: string
}
