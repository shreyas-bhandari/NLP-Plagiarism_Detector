import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import AppLayout from './layouts/AppLayout.jsx'
import Landing from './pages/Landing.jsx'
import Dashboard from './pages/Dashboard.jsx'
import NewAnalysis from './pages/NewAnalysis.jsx'
import AnalysisResults from './pages/AnalysisResults.jsx'
import ComparisonViewer from './pages/ComparisonViewer.jsx'
import History from './pages/History.jsx'
import Methodology from './pages/Methodology.jsx'
import NotFound from './pages/NotFound.jsx'
import { ToastProvider } from './components/Toast.jsx'

/** Scroll to top on navigation (the viewer manages its own scrolling). */
function ScrollReset() {
  const { pathname } = useLocation()
  useEffect(() => {
    if (!pathname.includes('/viewer')) window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <ToastProvider>
      <ScrollReset />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/analysis/new" element={<NewAnalysis />} />
          <Route path="/analysis/:analysisId" element={<AnalysisResults />} />
          <Route path="/analysis/:analysisId/viewer" element={<ComparisonViewer />} />
          <Route path="/history" element={<History />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/about" element={<Navigate to="/methodology" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </ToastProvider>
  )
}
