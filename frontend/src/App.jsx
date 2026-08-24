import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import CompaniesListPage from './pages/CompaniesListPage'
import CompanyDetailPage from './pages/CompanyDetailPage'
import ContentCalendarPage from './pages/ContentCalendarPage'
import BrandManagementPage from './pages/BrandManagementPage'
import AiStrategyPage from './pages/AiStrategyPage'
import CreativeGenerationPage from './pages/CreativeGenerationPage'
import VideoGenerationPage from './pages/VideoGenerationPage'
import TeamPage from './pages/TeamPage'
import './App.css'

function RootRedirect() {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <div className="page-loading">Loading…</div>
  return <Navigate to={isAuthenticated ? '/companies' : '/login'} replace />
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/companies" element={<CompaniesListPage />} />
            <Route path="/companies/:id" element={<CompanyDetailPage />} />
            <Route path="/companies/:id/calendar" element={<ContentCalendarPage />} />
            <Route path="/companies/:id/brand" element={<BrandManagementPage />} />
            <Route path="/companies/:id/ai-strategy" element={<AiStrategyPage />} />
            <Route path="/companies/:id/creative-generation" element={<CreativeGenerationPage />} />
            <Route path="/companies/:id/video-generation" element={<VideoGenerationPage />} />
            <Route path="/team" element={<TeamPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
