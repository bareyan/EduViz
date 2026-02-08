import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import HomePage from './pages/HomePage'
import AnalysisPage from './pages/AnalysisPage'
import GenerationPage from './pages/GenerationPage'
import ResultsPage from './pages/ResultsPage'
import GalleryPage from './pages/GalleryPage'
import EditPage from './pages/EditPage'
import LoginPage from './pages/LoginPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
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
  )
}

export default App
