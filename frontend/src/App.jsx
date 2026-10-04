import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import CompanyLayout from './components/CompanyLayout'
import LoginPage from './pages/LoginPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import './App.css'
import './styles/platform.css'

const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage'))
const CompaniesListPage = lazy(() => import('./pages/CompaniesListPage'))
const CompanyDetailPage = lazy(() => import('./pages/CompanyDetailPage'))
const ContentCalendarPage = lazy(() => import('./pages/ContentCalendarPage'))
const BrandManagementPage = lazy(() => import('./pages/BrandManagementPage'))
const AiStrategyPage = lazy(() => import('./pages/AiStrategyPage'))
const CreativeGenerationPage = lazy(() => import('./pages/CreativeGenerationPage'))
const VideoGenerationPage = lazy(() => import('./pages/VideoGenerationPage'))
const SocialAccountsPage = lazy(() => import('./pages/SocialAccountsPage'))
const MediaLibraryPage = lazy(() => import('./pages/MediaLibraryPage'))
const ContentReviewPage = lazy(() => import('./pages/ContentReviewPage'))
const PublishingPage = lazy(() => import('./pages/PublishingPage'))
const WhatsAppPage = lazy(() => import('./pages/WhatsAppPage'))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const CompanySubscriptionPage = lazy(() => import('./pages/CompanySubscriptionPage'))
const ApprovalsPage = lazy(() => import('./pages/ApprovalsPage'))
const PublishingQueuePage = lazy(() => import('./pages/PublishingQueuePage'))
const AnalyticsOverviewPage = lazy(() => import('./pages/AnalyticsOverviewPage'))
const AdminReportsPage = lazy(() => import('./pages/AdminReportsPage'))
const SubscriptionsPage = lazy(() => import('./pages/SubscriptionsPage'))
const WhatsAppTemplatesPage = lazy(() => import('./pages/WhatsAppTemplatesPage'))
const MusicLibraryPage = lazy(() => import('./pages/MusicLibraryPage'))
const SystemHealthPage = lazy(() => import('./pages/SystemHealthPage'))
const OAuthCallbackPage = lazy(() => import('./pages/OAuthCallbackPage'))
const TeamPage = lazy(() => import('./pages/TeamPage'))
const AccessControlPage = lazy(() => import('./pages/AccessControlPage'))
const ActivityLogPage = lazy(() => import('./pages/ActivityLogPage'))
const JobsPage = lazy(() => import('./pages/JobsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const AdminSettingsPage = lazy(() => import('./pages/AdminSettingsPage'))
const PromptTemplatesPage = lazy(() => import('./pages/PromptTemplatesPage'))
const ClientDashboardPage = lazy(() => import('./pages/ClientDashboardPage'))

function RootRedirect() {
  const { isAuthenticated, isAdmin, loading } = useAuth()
  if (loading) return <div className="page-loading">Loading…</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Navigate to={isAdmin ? '/dashboard' : '/client'} replace />
}

function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<div className="page-loading">Loading…</div>}>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<AdminDashboardPage />} />
            <Route path="/companies" element={<CompaniesListPage />} />

            {/* Company workspace - every module shares the company navigation */}
            <Route path="/companies/:id" element={<CompanyLayout />}>
              <Route index element={<CompanyDetailPage />} />
              <Route path="brand" element={<BrandManagementPage />} />
              <Route path="ai-strategy" element={<AiStrategyPage />} />
              <Route path="calendar" element={<ContentCalendarPage />} />
              <Route path="creative-generation" element={<CreativeGenerationPage />} />
              <Route path="video-generation" element={<VideoGenerationPage />} />
              <Route path="approvals" element={<ContentReviewPage />} />
              <Route path="publishing" element={<PublishingPage />} />
              <Route path="social-accounts" element={<SocialAccountsPage />} />
              <Route path="whatsapp" element={<WhatsAppPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="media-library" element={<MediaLibraryPage />} />
              <Route path="subscription" element={<CompanySubscriptionPage />} />
            </Route>

            <Route path="/client" element={<ClientDashboardPage />} />
            <Route path="/approvals" element={<ApprovalsPage />} />
            <Route path="/publishing" element={<PublishingQueuePage />} />
            <Route path="/analytics" element={<AnalyticsOverviewPage />} />
            <Route path="/reports" element={<AdminReportsPage />} />
            <Route path="/subscriptions" element={<SubscriptionsPage />} />
            <Route path="/whatsapp" element={<WhatsAppTemplatesPage />} />
            <Route path="/music-library" element={<MusicLibraryPage />} />
            <Route path="/system-health" element={<SystemHealthPage />} />
            <Route path="/oauth/callback/:provider" element={<OAuthCallbackPage />} />
            <Route path="/team" element={<TeamPage />} />
            <Route path="/access" element={<AccessControlPage />} />
            <Route path="/activity-log" element={<ActivityLogPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin-settings" element={<AdminSettingsPage />} />
            <Route path="/prompt-templates" element={<PromptTemplatesPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </AuthProvider>
  )
}

export default App
