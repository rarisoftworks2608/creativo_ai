import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import AdminDashboardPage from './pages/AdminDashboardPage'
import CompaniesListPage from './pages/CompaniesListPage'
import CompanyDetailPage from './pages/CompanyDetailPage'
import ContentCalendarPage from './pages/ContentCalendarPage'
import BrandManagementPage from './pages/BrandManagementPage'
import AiStrategyPage from './pages/AiStrategyPage'
import CreativeGenerationPage from './pages/CreativeGenerationPage'
import VideoGenerationPage from './pages/VideoGenerationPage'
import SocialAccountsPage from './pages/SocialAccountsPage'
import MediaLibraryPage from './pages/MediaLibraryPage'
import TeamPage from './pages/TeamPage'
import AccessControlPage from './pages/AccessControlPage'
import ClientDashboardPage from './pages/ClientDashboardPage'
import './App.css'

function RootRedirect() {
  const { isAuthenticated, isAdmin, loading } = useAuth()
  if (loading) return <div className="page-loading">Loading…</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Navigate to={isAdmin ? '/dashboard' : '/client'} replace />
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<AdminDashboardPage />} />
            <Route path="/companies" element={<CompaniesListPage />} />
            <Route path="/companies/:id" element={<CompanyDetailPage />} />
            <Route path="/companies/:id/calendar" element={<ContentCalendarPage />} />
            <Route path="/companies/:id/brand" element={<BrandManagementPage />} />
            <Route path="/companies/:id/ai-strategy" element={<AiStrategyPage />} />
            <Route path="/companies/:id/creative-generation" element={<CreativeGenerationPage />} />
            <Route path="/companies/:id/video-generation" element={<VideoGenerationPage />} />
            <Route path="/companies/:id/social-accounts" element={<SocialAccountsPage />} />
            <Route path="/companies/:id/media-library" element={<MediaLibraryPage />} />
            <Route path="/client" element={<ClientDashboardPage />} />
            <Route path="/team" element={<TeamPage />} />
            <Route path="/access" element={<AccessControlPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
