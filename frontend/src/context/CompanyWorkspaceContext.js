import { createContext, useContext } from 'react'

export const CompanyWorkspaceContext = createContext(null)

export function useCompanyWorkspace() {
  return useContext(CompanyWorkspaceContext)
}

// Every module inside a company workspace. `page` is the client page permission that
// gates it (Access Control); `adminOnly` modules never show to clients.
export const COMPANY_MODULES = [
  { path: '', label: 'Overview', adminOnly: true, end: true },
  { path: 'brand', label: 'Brand', page: 'brand' },
  { path: 'ai-strategy', label: 'Strategy', page: 'ai_strategy' },
  { path: 'calendar', label: 'Calendar', page: 'calendar' },
  { path: 'creative-generation', label: 'Creatives', page: 'creative_generation' },
  { path: 'video-generation', label: 'Videos', page: 'video_generation' },
  { path: 'approvals', label: 'Approvals', page: 'calendar' },
  { path: 'publishing', label: 'Publishing', page: 'publishing' },
  { path: 'social-accounts', label: 'Social accounts', adminOnly: true },
  { path: 'whatsapp', label: 'WhatsApp', adminOnly: true },
  { path: 'analytics', label: 'Analytics', page: 'analytics' },
  { path: 'reports', label: 'Reports', page: 'reports' },
  { path: 'media-library', label: 'Media', adminOnly: true },
  { path: 'subscription', label: 'Subscription', page: 'subscription' },
]

export function visibleModules(isAdmin, permissions = []) {
  return COMPANY_MODULES.filter((module) => (isAdmin ? true : !module.adminOnly && permissions.includes(module.page)))
}
