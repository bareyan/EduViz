export interface PipelineInfo {
  name: string
  description: string
  is_active: boolean
  models: {
    script_generation: string
    manim_generation: string
    visual_script_generation: string
    analysis?: string
    animation_refinement?: string
  }
}

export interface PipelinesResponse {
  pipelines: PipelineInfo[]
  active: string
}
