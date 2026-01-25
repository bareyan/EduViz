# Pipeline Selection Feature

## Overview
Users can now select which AI model pipeline to use when generating videos. This allows choosing between balanced quality, maximum quality, or cost-optimized generation.

## Available Pipelines

### 1. Default Pipeline
- **Description**: Balanced quality and speed - best for most use cases
- **Models**:
  - Script Generation: `gemini-2.0-flash-exp`
  - Visual Script: `gemini-2.0-flash-exp`
  - Manim Generation: `gemini-2.0-flash-exp`

### 2. High Quality Pipeline
- **Description**: Maximum quality with stronger models and deeper thinking
- **Models**:
  - Script Generation: `gemini-3-flash-preview`
  - Visual Script: `gemini-3-flash-preview`
  - Manim Generation: `gemini-3-pro-preview`

### 3. Cost Optimized Pipeline
- **Description**: Budget-friendly with fastest models
- **Models**:
  - Script Generation: `gemini-flash-lite-latest`
  - Visual Script: `gemini-flash-lite-latest`
  - Manim Generation: `gemini-flash-lite-latest`

## Backend Implementation

### Configuration (`backend/app/config/models.py`)
- Added `AVAILABLE_PIPELINES` dictionary containing all pipeline configurations
- Added `set_active_pipeline(pipeline_name: str)` function to switch pipelines at runtime
- Added `get_active_pipeline_name()` to retrieve current pipeline
- Modified `get_model_config()` to accept optional `pipeline` parameter

### API Endpoint (`backend/app/routes/generation.py`)
- `GET /pipelines`: Returns list of available pipelines with descriptions and model details
- `POST /generate`: Now accepts `pipeline` field in request body

### Generation Flow
1. User selects pipeline in UI
2. Frontend sends pipeline name in generation request
3. Backend calls `set_active_pipeline()` before starting generation
4. All services (ScriptGenerator, ManimGenerator) use the selected pipeline's models

## Frontend Implementation

### API Client (`frontend/src/api/index.ts`)
Added types and functions:
```typescript
export interface PipelineInfo {
  name: string
  description: string
  is_active: boolean
  models: {
    script_generation: string
    manim_generation: string
    visual_script_generation: string
  }
}

export interface PipelinesResponse {
  pipelines: PipelineInfo[]
  active: string
}

export async function getPipelines(): Promise<PipelinesResponse>
```

Updated `generateVideos()` to accept `pipeline?: string` parameter.

### UI Component (`frontend/src/pages/GenerationPage.tsx`)
Added:
- State for storing available pipelines and selected pipeline
- `useEffect` hook to load pipelines on mount
- Pipeline selection UI section with card-based selection
- Each pipeline card shows:
  - Name (formatted)
  - Description
  - Active indicator (if currently active)
  - Model details for each generation step

The pipeline selector is placed between "Document Context" and "Language & Voice" sections in the generation page.

## Usage

### For Users
1. Navigate to the generation page after selecting topics
2. Scroll to the "AI Model Pipeline" section
3. Click on the desired pipeline card:
   - **Default**: Recommended for most users - good balance of quality and speed
   - **High Quality**: Use when you need the best possible output and have more time/budget
   - **Cost Optimized**: Use for testing or when budget is a primary concern
4. Continue configuring other settings (language, voice, etc.)
5. Click "Generate Videos" - the selected pipeline will be used

### For Developers
To add a new pipeline:
1. Add it to `AVAILABLE_PIPELINES` in `backend/app/config/models.py`
2. Define the `PipelineModels` with appropriate model configurations
3. Add description logic in `get_available_pipelines()` route handler
4. The UI will automatically pick it up

## Testing
To verify the feature:
1. Start the backend server
2. Test the `/pipelines` endpoint:
   ```bash
   curl http://localhost:8000/pipelines
   ```
3. Generate a video with each pipeline and compare:
   - Generation time
   - Output quality
   - API costs (if tracking enabled)

## Future Enhancements
- [ ] Add cost estimation per pipeline
- [ ] Show estimated generation time for each pipeline
- [ ] Allow saving pipeline preferences per user
- [ ] Add custom pipeline builder UI
- [ ] Track usage statistics per pipeline
