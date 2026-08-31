// Small inline icon set shared by AdminDashboardPage and ClientDashboardPage,
// so both pages draw from the same visual language instead of duplicating SVGs.
const ICONS = {
  building: (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M4 17V4.5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1V17" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M12 8h3a1 1 0 0 1 1 1v8" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M2.5 17h15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6.5 6.5h1M6.5 9.5h1M6.5 12.5h1M9.5 6.5h1M9.5 9.5h1M9.5 12.5h1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M4 10.5l3.5 3.5L16 5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 20 20" fill="none">
      <circle cx="7" cy="6.5" r="2.75" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.5 16.5c0-2.9 2.24-4.75 4.5-4.75s4.5 1.85 4.5 4.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="14" cy="6.5" r="2.25" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12.5 12c1.9.35 3.5 1.9 3.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  sparkle: (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M10 3l1.4 4.1L15.5 8.5l-4.1 1.4L10 14l-1.4-4.1L4.5 8.5l4.1-1.4L10 3Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M15.5 13l.6 1.8 1.9.7-1.9.6-.6 1.9-.6-1.9-1.9-.6 1.9-.7.6-1.8Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  ),
  clock: (
    <svg viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 6v4l2.6 1.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  alert: (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M10 3.5 17.5 16h-15L10 3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M10 8.3v3.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="13.7" r="0.9" fill="currentColor" />
    </svg>
  ),
  dollar: (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M10 2.5v15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13.5 6.2c0-1.5-1.6-2.2-3.5-2.2s-3.5.9-3.5 2.5c0 1.7 1.6 2.3 3.5 2.5s3.5.7 3.5 2.5c0 1.6-1.6 2.5-3.5 2.5s-3.5-.7-3.5-2.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  image: (
    <svg viewBox="0 0 20 20" fill="none">
      <rect x="2.5" y="3.5" width="15" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="7" cy="8" r="1.4" stroke="currentColor" strokeWidth="1.4" />
      <path d="M3.5 14.5 8 10.5l2.5 2.3 2.7-3.3 3.3 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 20 20" fill="none">
      <rect x="2.5" y="4" width="15" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.5 8h15" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6.5 2.5v3M13.5 2.5v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6 11.5h1.5M9.25 11.5h1.5M12.5 11.5H14M6 14.5h1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
}

export default ICONS
