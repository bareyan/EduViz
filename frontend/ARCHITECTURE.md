# Frontend Architecture

**Deep Dive into EduViz Frontend Design**

For a high-level system overview, see [Root Architecture](../ARCHITECTURE.md).

---

## Directory Structure

```
frontend/
├── src/
│   ├── App.tsx                   # Main application & routing
│   ├── main.tsx                  # Application entry point
│   ├── index.css                 # Global styles (Tailwind)
│   ├── pages/                    # Route components (Views)
│   │   ├── HomePage.tsx          # Upload interface
│   │   ├── AnalysisPage.tsx      # Topic selection
│   │   ├── GenerationPage.tsx    # Video generation process
│   │   ├── ResultsPage.tsx       # Video playback
│   │   ├── EditPage.tsx          # Section editing
│   │   ├── GalleryPage.tsx       # Job gallery
│   │   └── LoginPage.tsx         # Authentication
│   ├── features/                 # Feature-specific components
│   ├── services/                 # API client services
│   ├── hooks/                    # Custom React hooks
│   ├── types/                    # TypeScript interfaces
│   ├── config/                   # Configuration
│   └── components/               # Shared UI components
```

## Component Architecture

### Page Components (`pages/`)

**Responsibility**: Top-level route components that compose features.

- **HomePage**: Drag-and-drop file upload, initial configuration
- **AnalysisPage**: Topic selection, customization, reordering
- **GenerationPage**: Real-time progress tracking, job status
- **ResultsPage**: Video playback, section navigation
- **EditPage**: Section-level editing, regeneration
- **GalleryPage**: Job history, thumbnail grid
- **LoginPage**: Authentication interface

### Feature Components (`features/`)

**Responsibility**: Domain-specific, reusable components.

Examples:
- `VideoPlayer` - Custom video player with controls
- `TopicCard` - Topic selection card with edit capabilities
- `ProgressTracker` - Real-time job progress visualization
- `SectionEditor` - Section content editing interface

### Shared Components (`components/`)

**Responsibility**: Generic, reusable UI primitives.

Examples:
- `Layout` - Application shell with navigation
- `RequireAuth` - Authentication guard
- Buttons, Inputs, Modals, etc.

## State Management

### Local State (React Hooks)

Used for component-specific state:
- Form inputs
- UI toggles
- Temporary data

### API State (React Hooks + Services)

Managed through custom hooks in `hooks/`:
- `useJob` - Job status polling
- `useAnalysis` - Content analysis state
- `useGeneration` - Video generation state

### Global State (Context API)

**AuthContext** (`contexts/AuthContext.tsx`):
- Authentication status
- User session management
- Login/logout handlers

## Routing Structure

```typescript
// App.tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route element={<RequireAuth />}>           // Protected routes
    <Route path="/" element={<Layout />}>
      <Route index element={<HomePage />} />
      <Route path="gallery" element={<GalleryPage />} />
      <Route path="analysis/:fileId" element={<AnalysisPage />} />
      <Route path="generate/:analysisId" element={<GenerationPage />} />
      <Route path="results/:jobId" element={<ResultsPage />} />
      <Route path="edit/:jobId" element={<EditPage />} />
    </Route>
  </Route>
</Routes>
```

## API Integration

### Configuration (`config/api.config.ts`)

Centralized API base URL configuration.

### Services (`services/`)

Axios-based API clients for each domain:
- `jobService` - Job management operations
- `uploadService` - File upload handling
- `analysisService` - Content analysis
- `generationService` - Video generation

**Pattern**:
```typescript
// Example service
export const jobService = {
  getJob: (jobId: string) => api.get(`/jobs/${jobId}`),
  getSections: (jobId: string) => api.get(`/jobs/${jobId}/sections`),
  updateSection: (jobId: string, sectionId: string, data: any) => 
    api.patch(`/jobs/${jobId}/sections/${sectionId}`, data)
};
```

## User Flow

```
Upload (HomePage)
    ↓
Analysis (AnalysisPage) - Select/customize topics
    ↓
Generation (GenerationPage) - Configure & generate
    ↓
Results (ResultsPage) - Watch & review
    ↓ (optional)
Edit (EditPage) - Modify sections
    ↓
Gallery (GalleryPage) - Browse all jobs
```

## Styling Approach

- **TailwindCSS**: Utility-first styling
- **Responsive Design**: Mobile-first breakpoints
- **Custom Theme**: Consistent color palette and spacing

## Type Safety

All components use TypeScript with strict typing:
- Props interfaces
- API response types (`types/`)
- Hook return types

## Performance Optimizations

- **Code Splitting**: Route-based lazy loading (future enhancement)
- **Thumbnail Loading**: Fast gallery with video thumbnails
- **Status Polling**: Efficient job status updates
- **Memoization**: React.memo for expensive components (when needed)

## Development Workflow

1. **Local Dev**: `npm run dev` - Hot module replacement
2. **Type Checking**: Automatic via TypeScript compiler
3. **Linting**: ESLint for code quality
4. **Build**: `npm run build` - Production bundle
