import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import AnalysisPage from './pages/AnalysisPage'
import GenerationPage from './pages/GenerationPage'
import ResultsPage from './pages/ResultsPage'
import GalleryPage from './pages/GalleryPage'
import EditPage from './pages/EditPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="gallery" element={<GalleryPage />} />
        <Route path="analysis/:fileId" element={<AnalysisPage />} />
        <Route path="generate/:analysisId" element={<GenerationPage />} />
        <Route path="results/:jobId" element={<ResultsPage />} />
        <Route path="edit/:jobId" element={<EditPage />} />
      </Route>
    </Routes>
  )
}

export default App
