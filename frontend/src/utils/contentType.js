// Mirrors apps.content_calendar.tasks.VIDEO_KEYWORDS / _is_video on the backend -
// which pipeline (image or video) a calendar item's free-text content_type maps to.
const VIDEO_KEYWORDS = ['reel', 'video', 'short']

export function isVideoContentType(contentType) {
  const normalized = (contentType || '').toLowerCase()
  return VIDEO_KEYWORDS.some((keyword) => normalized.includes(keyword))
}
