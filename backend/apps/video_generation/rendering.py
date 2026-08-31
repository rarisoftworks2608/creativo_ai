"""FFmpeg-based video rendering (Epic 07: Video Processing).

Requires the `ffmpeg` binary on PATH - this is a separate program, not a
pip package, and must be installed on the machine running the Celery
worker. It cannot be `pip install`ed:
  - Windows: https://www.gyan.dev/ffmpeg/builds/ (download, add the `bin`
    folder to PATH, restart the terminal)
  - macOS:   brew install ffmpeg
  - Linux:   apt install ffmpeg / dnf install ffmpeg

If it's missing, rendering fails with a clear FFmpegNotAvailable error
(caught by tasks.py and surfaced as the request's error_message) instead
of crashing - the same "fail clearly, don't crash" contract as a missing
AI provider API key.

Approach: each scene becomes a short clip - its AI-generated motion clip
(video_client.py) if one was made, looped/trimmed to the scene's duration,
otherwise its still image with a slow zoom/pan - with that scene's voice-over
as its audio track. All clips are then joined with the concat demuxer
(reliable for same-codec clips, unlike a single complex filter graph), then
the logo overlay and subtitle burn-in are each a further single-pass filter
over the joined video.

Only works with local (FileSystemStorage) media files, since it needs real
filesystem paths (`FieldFile.path`) - consistent with the rest of the
project, which doesn't have S3/remote storage wired up yet either.
"""

import os
import shutil
import subprocess
import tempfile

from common.ai_errors import AIProviderError

ASPECT_RATIO_RESOLUTIONS = {
    '9:16': (1080, 1920),
    '1:1': (1080, 1080),
    '16:9': (1920, 1080),
}

LOGO_MARGIN = 24
LOGO_WIDTH = 140


class FFmpegNotAvailable(AIProviderError):
    """Raised when the `ffmpeg` binary can't be found on PATH."""


def check_ffmpeg_available():
    if shutil.which('ffmpeg') is None:
        raise FFmpegNotAvailable(
            'FFmpeg is not installed on this server. Install the ffmpeg binary and make sure it is on PATH.'
        )


def _run(args):
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or str(exc))[-2000:]
        raise AIProviderError(f'FFmpeg failed: {detail}') from exc


def _render_scene_clip(scene, width, height, output_path):
    """Renders one scene into a clip: its voice-over, over either its AI-generated
    motion clip (looped/trimmed to the scene duration) if one was generated, or
    - falling back - its still image with a slow zoom/pan.
    """
    duration = max(scene.duration_seconds, 0.5)
    has_ai_clip = bool(scene.video_clip and os.path.exists(scene.video_clip.path))

    if has_ai_clip:
        args = ['ffmpeg', '-y', '-stream_loop', '-1', '-i', scene.video_clip.path]
        video_filter = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}'
    else:
        zoom_frames = max(int(duration * 25), 1)
        args = ['ffmpeg', '-y', '-loop', '1', '-i', scene.image.path]
        video_filter = (
            f'scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,'
            f'crop={width * 2}:{height * 2},'
            f"zoompan=z='min(zoom+0.0015,1.2)':d={zoom_frames}:s={width}x{height}:fps=25"
        )

    has_audio = bool(scene.voice_over_audio and os.path.exists(scene.voice_over_audio.path))
    if has_audio:
        args += ['-i', scene.voice_over_audio.path]
    else:
        args += ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']

    args += [
        '-vf', video_filter,
        '-t', str(duration),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-shortest',
        output_path,
    ]
    _run(args)


def _concat_clips(clip_paths, output_path, work_dir):
    filelist_path = os.path.join(work_dir, 'filelist.txt')
    with open(filelist_path, 'w', encoding='utf-8') as f:
        for path in clip_paths:
            escaped = path.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    _run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', filelist_path, '-c', 'copy', output_path])


def _overlay_logo(input_path, logo_path, output_path):
    filter_complex = f'[1:v]scale={LOGO_WIDTH}:-1[logo];[0:v][logo]overlay=W-w-{LOGO_MARGIN}:H-h-{LOGO_MARGIN}'
    _run([
        'ffmpeg', '-y', '-i', input_path, '-i', logo_path,
        '-filter_complex', filter_complex, '-c:a', 'copy', output_path,
    ])


def _burn_subtitles(input_path, srt_path, output_path):
    escaped_srt = srt_path.replace('\\', '/').replace(':', '\\:')
    _run(['ffmpeg', '-y', '-i', input_path, '-vf', f"subtitles='{escaped_srt}'", '-c:a', 'copy', output_path])


def _extract_thumbnail(video_path, thumbnail_path, at_seconds):
    _run(['ffmpeg', '-y', '-ss', str(at_seconds), '-i', video_path, '-vframes', '1', thumbnail_path])


def render_video(*, scenes, aspect_ratio, subtitles_srt='', logo_path=None, include_logo=True):
    """Renders the final video from a list of VideoScene rows (in scene order).

    Returns (video_bytes, thumbnail_bytes, duration_seconds, resolution_str).
    """
    check_ffmpeg_available()
    if not scenes:
        raise AIProviderError('No scenes to render.')

    width, height = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, ASPECT_RATIO_RESOLUTIONS['9:16'])

    with tempfile.TemporaryDirectory(prefix='video_render_') as work_dir:
        clip_paths = []
        for scene in scenes:
            clip_path = os.path.join(work_dir, f'scene_{scene.scene_number}.mp4')
            _render_scene_clip(scene, width, height, clip_path)
            clip_paths.append(clip_path)

        current_path = os.path.join(work_dir, 'concatenated.mp4')
        _concat_clips(clip_paths, current_path, work_dir)

        if include_logo and logo_path and os.path.exists(logo_path):
            with_logo_path = os.path.join(work_dir, 'with_logo.mp4')
            _overlay_logo(current_path, logo_path, with_logo_path)
            current_path = with_logo_path

        if subtitles_srt.strip():
            srt_path = os.path.join(work_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(subtitles_srt)
            with_subs_path = os.path.join(work_dir, 'with_subs.mp4')
            _burn_subtitles(current_path, srt_path, with_subs_path)
            current_path = with_subs_path

        total_duration = sum(max(s.duration_seconds, 0.5) for s in scenes)
        thumbnail_path = os.path.join(work_dir, 'thumbnail.jpg')
        _extract_thumbnail(current_path, thumbnail_path, at_seconds=min(1.0, total_duration / 2))

        with open(current_path, 'rb') as f:
            video_bytes = f.read()
        with open(thumbnail_path, 'rb') as f:
            thumbnail_bytes = f.read()

    return video_bytes, thumbnail_bytes, total_duration, f'{width}x{height}'
