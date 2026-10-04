import VariationGrid from './VariationGrid'

// The latest generated creative variations or video for a calendar item - shared by the
// approvals queue, the content review page and the publishing scheduler.
export default function ContentPreview({ item, onSelectVariation, selectingId }) {
  const generation = item.latest_generation_request
  const video = item.latest_video_request
  const useVideo = video && (!generation || new Date(video.created_at) >= new Date(generation.created_at))

  if (useVideo) {
    if (video.status === 'succeeded' && video.video_file) {
      return (
        <div className="content-preview-video">
          <video controls src={video.video_file} poster={video.thumbnail || undefined} className="video-preview" />
          {video.script && (
            <details className="script-details">
              <summary>Read the script</summary>
              <p className="variation-caption">{video.script}</p>
            </details>
          )}
        </div>
      )
    }
    return <p className="page-subtitle">Video is {video.status === 'failed' ? 'unavailable (generation failed)' : 'still being generated…'}</p>
  }

  if (generation) {
    if (generation.status === 'succeeded' && generation.variations.length > 0) {
      return (
        <VariationGrid
          variations={generation.variations}
          onSelect={onSelectVariation}
          selecting={selectingId}
        />
      )
    }
    return (
      <p className="page-subtitle">
        Creative is {generation.status === 'failed' ? 'unavailable (generation failed)' : 'still being generated…'}
      </p>
    )
  }

  return <p className="page-subtitle">No generated content yet.</p>
}
