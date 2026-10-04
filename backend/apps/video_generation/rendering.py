"""FFmpeg-based video rendering (Epic 07: Video Processing - Rendering, FFmpeg, Aspect
ratio, Resolution, Duration, Compression, Thumbnail).

FFmpeg is located in this order (see find_ffmpeg):
  1. settings.FFMPEG_BINARY (a full path, e.g. C:/ffmpeg/bin/ffmpeg.exe)
  2. `ffmpeg` on PATH
       - Windows: `winget install Gyan.FFmpeg` (or download from gyan.dev and add bin/ to PATH)
       - macOS:   `brew install ffmpeg`
       - Linux:   `apt install ffmpeg` (already in the backend Docker image)
  3. the static binary shipped by the optional `imageio-ffmpeg` pip package
If none is found, rendering fails with a clear FFmpegNotAvailable error (surfaced as the
request's error_message) instead of crashing.

Pipeline:
  1. each scene -> a short clip: its AI motion clip (looped/trimmed) if one was made,
     otherwise its still image with a slow zoom/pan, with that scene's voice-over
  2. optional brand outro card (brand colour + logo + name + CTA)
  3. clips joined with the concat demuxer
  4. ONE final encode: logo overlay, burned-in subtitles, background music mixed under
     the voice, H.264 CRF compression and +faststart (required for smooth playback and
     Instagram/Facebook processing)
  5. thumbnail extracted from the result

Works with any Django storage backend: files that aren't on local disk (S3/R2) are
downloaded to the temp working directory first.
"""

import os
import shutil
import subprocess
import tempfile

from django.conf import settings

from common.ai_errors import AIProviderError

ASPECT_RATIO_RESOLUTIONS = {
    '9:16': (1080, 1920),
    '1:1': (1080, 1080),
    '16:9': (1920, 1080),
}

LOGO_MARGIN = 24
LOGO_WIDTH = 140
FPS = 25
OUTRO_SECONDS = 2.5


class FFmpegNotAvailable(AIProviderError):
    """Raised when no FFmpeg binary can be found."""


def find_ffmpeg():
    configured = getattr(settings, 'FFMPEG_BINARY', '')
    if configured and os.path.exists(configured):
        return configured
    on_path = shutil.which('ffmpeg')
    if on_path:
        return on_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - package not installed / binary missing
        return None


def check_ffmpeg_available():
    binary = find_ffmpeg()
    if not binary:
        raise FFmpegNotAvailable(
            'FFmpeg is not installed on this server. Install it (Windows: `winget install Gyan.FFmpeg`, '
            'macOS: `brew install ffmpeg`, Linux: `apt install ffmpeg`) or set FFMPEG_BINARY in .env to its full path.'
        )
    return binary


def _run(args):
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or str(exc))[-2000:]
        raise AIProviderError(f'FFmpeg failed: {detail}') from exc


def materialize(field, work_dir, name):
    """A local filesystem path for a FieldFile - its own path on local storage, otherwise a
    temp copy (S3/R2). Returns None if the field is empty or the file is missing."""
    if not field:
        return None
    try:
        path = field.path
        if os.path.exists(path):
            return path
    except (NotImplementedError, ValueError):
        pass
    try:
        ext = os.path.splitext(field.name)[1] or ''
        local_path = os.path.join(work_dir, f'{name}{ext}')
        with field.open('rb') as source, open(local_path, 'wb') as target:
            shutil.copyfileobj(source, target)
        return local_path
    except (FileNotFoundError, OSError):
        return None


def _encoding_args():
    return [
        '-c:v', 'libx264', '-preset', str(getattr(settings, 'VIDEO_PRESET', 'veryfast')),
        '-crf', str(getattr(settings, 'VIDEO_CRF', 23)), '-pix_fmt', 'yuv420p', '-r', str(FPS),
    ]


def _render_scene_clip(ffmpeg, scene, width, height, output_path, work_dir):
    duration = max(scene.duration_seconds, 0.5)
    clip_path = materialize(scene.video_clip, work_dir, f'scene_{scene.scene_number}_clip')
    image_path = materialize(scene.image, work_dir, f'scene_{scene.scene_number}_image')
    if not clip_path and not image_path:
        raise AIProviderError(f'Scene {scene.scene_number} has no image to render.')

    if clip_path:
        args = [ffmpeg, '-y', '-stream_loop', '-1', '-i', clip_path]
        video_filter = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={FPS}'
    else:
        zoom_frames = max(int(duration * FPS), 1)
        args = [ffmpeg, '-y', '-loop', '1', '-i', image_path]
        video_filter = (
            f'scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,'
            f'crop={width * 2}:{height * 2},'
            f"zoompan=z='min(zoom+0.0015,1.2)':d={zoom_frames}:s={width}x{height}:fps={FPS}"
        )

    audio_path = materialize(scene.voice_over_audio, work_dir, f'scene_{scene.scene_number}_audio')
    if audio_path:
        args += ['-i', audio_path]
    else:
        args += ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100']

    args += [
        '-vf', video_filter, '-t', str(duration), *_encoding_args(),
        '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-shortest', output_path,
    ]
    _run(args)


def _hex_to_rgb(value, fallback=(31, 26, 46)):
    value = (value or '').strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return fallback


def _outro_image(outro, width, height, path):
    """Brand end card: brand colour background, logo, company name and CTA/website."""
    from PIL import Image, ImageDraw, ImageFont

    background = _hex_to_rgb(outro.get('color'))
    luminance = 0.299 * background[0] + 0.587 * background[1] + 0.114 * background[2]
    ink = (20, 18, 28) if luminance > 160 else (255, 255, 255)
    canvas = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(canvas)

    font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'creative_generation', 'fonts')

    def font(name, size):
        try:
            return ImageFont.truetype(os.path.join(font_dir, name), size)
        except OSError:
            return ImageFont.load_default()

    y = height * 0.30
    logo_path = outro.get('logo_path')
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert('RGBA')
            max_w, max_h = int(width * 0.45), int(height * 0.18)
            logo.thumbnail((max_w, max_h))
            canvas.paste(logo, ((width - logo.width) // 2, int(y)), logo)
            y += logo.height + height * 0.05
        except OSError:
            pass

    for text, face, size_ratio in (
        (outro.get('title', ''), 'PlayfairDisplay-Variable.ttf', 0.055 if width < height else 0.045),
        (outro.get('subtitle', ''), 'Poppins-SemiBold.ttf', 0.03 if width < height else 0.026),
    ):
        if not text:
            continue
        size = int(min(width, height) * size_ratio * (1.6 if width < height else 1.0))
        face_font = font(face, size)
        words, lines, line = text.split(), [], ''
        for word in words:
            candidate = f'{line} {word}'.strip()
            if draw.textlength(candidate, font=face_font) > width * 0.82 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        for text_line in lines[:3]:
            text_width = draw.textlength(text_line, font=face_font)
            draw.text(((width - text_width) / 2, y), text_line, font=face_font, fill=ink)
            y += size * 1.3
        y += size * 0.4

    canvas.save(path, 'PNG')


def _render_outro_clip(ffmpeg, outro, width, height, output_path, work_dir):
    image_path = os.path.join(work_dir, 'outro.png')
    _outro_image(outro, width, height, image_path)
    _run([
        ffmpeg, '-y', '-loop', '1', '-i', image_path,
        '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
        '-vf', f'fade=t=in:st=0:d=0.4,fps={FPS}', '-t', str(OUTRO_SECONDS), *_encoding_args(),
        '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-shortest', output_path,
    ])


def _concat_clips(ffmpeg, clip_paths, output_path, work_dir):
    filelist_path = os.path.join(work_dir, 'filelist.txt')
    with open(filelist_path, 'w', encoding='utf-8') as f:
        for path in clip_paths:
            escaped = path.replace('\\', '/').replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    _run([ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', filelist_path, '-c', 'copy', output_path])


def _subtitle_filter(srt_path, width, height):
    escaped = srt_path.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
    font_size = 13 if width < height else 18
    style = (
        f'FontName=Arial,FontSize={font_size},PrimaryColour=&H00FFFFFF,BackColour=&H99000000,'
        'BorderStyle=4,Outline=0,Shadow=0,MarginV=70,Alignment=2'
    )
    return f"subtitles='{escaped}':force_style='{style}'"


def _final_pass(ffmpeg, input_path, output_path, *, logo_path, srt_path, music_path, music_volume,
                total_duration, has_voice, width, height):
    """One encode for logo + subtitles + music + compression."""
    args = [ffmpeg, '-y', '-i', input_path]
    filters = []
    video_label = '0:v'
    next_input = 1

    if logo_path:
        args += ['-i', logo_path]
        filters.append(f'[{next_input}:v]scale={LOGO_WIDTH}:-1[logo]')
        filters.append(f'[{video_label}][logo]overlay=W-w-{LOGO_MARGIN}:H-h-{LOGO_MARGIN}[vlogo]')
        video_label = 'vlogo'
        next_input += 1

    if srt_path:
        filters.append(f'[{video_label}]{_subtitle_filter(srt_path, width, height)}[vsubs]')
        video_label = 'vsubs'

    audio_label = '0:a'
    if music_path:
        args += ['-stream_loop', '-1', '-i', music_path]
        fade_start = max(total_duration - 2.0, 0)
        volume = music_volume if has_voice else max(music_volume, 0.6)
        filters.append(
            f'[{next_input}:a]volume={volume},atrim=0:{total_duration:.2f},asetpts=PTS-STARTPTS,'
            f'afade=t=out:st={fade_start:.2f}:d=2[bg]'
        )
        filters.append('[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0,volume=2[aout]')
        audio_label = 'aout'
        next_input += 1

    if filters:
        args += ['-filter_complex', ';'.join(filters)]
    args += ['-map', f'[{video_label}]' if video_label != '0:v' else '0:v']
    args += ['-map', f'[{audio_label}]' if audio_label != '0:a' else '0:a']
    args += [*_encoding_args(), '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-t', f'{total_duration:.2f}', output_path]
    _run(args)


def _extract_thumbnail(ffmpeg, video_path, thumbnail_path, at_seconds):
    _run([ffmpeg, '-y', '-ss', str(at_seconds), '-i', video_path, '-vframes', '1', '-q:v', '3', thumbnail_path])


def render_video(*, scenes, aspect_ratio, subtitles_srt='', logo_path=None, include_logo=True,
                 music_field=None, music_volume=0.15, outro=None):
    """Renders the final video from a list of VideoScene rows (in scene order).

    `logo_path` may be a local path or a FieldFile; `music_field` a FieldFile (or path);
    `outro` a dict {color, title, subtitle, logo_path} or None.
    Returns (video_bytes, thumbnail_bytes, duration_seconds, resolution_str).
    """
    ffmpeg = check_ffmpeg_available()
    if not scenes:
        raise AIProviderError('No scenes to render.')

    width, height = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, ASPECT_RATIO_RESOLUTIONS['9:16'])

    with tempfile.TemporaryDirectory(prefix='video_render_') as work_dir:
        def local(value, name):
            if value is None or value == '':
                return None
            if isinstance(value, str):
                return value if os.path.exists(value) else None
            return materialize(value, work_dir, name)

        clip_paths = []
        for scene in scenes:
            clip_path = os.path.join(work_dir, f'scene_{scene.scene_number}.mp4')
            _render_scene_clip(ffmpeg, scene, width, height, clip_path, work_dir)
            clip_paths.append(clip_path)

        total_duration = sum(max(s.duration_seconds, 0.5) for s in scenes)
        if outro:
            outro = {**outro, 'logo_path': local(outro.get('logo_path'), 'outro_logo')}
            outro_path = os.path.join(work_dir, 'outro.mp4')
            _render_outro_clip(ffmpeg, outro, width, height, outro_path, work_dir)
            clip_paths.append(outro_path)
            total_duration += OUTRO_SECONDS

        concatenated = os.path.join(work_dir, 'concatenated.mp4')
        _concat_clips(ffmpeg, clip_paths, concatenated, work_dir)

        srt_path = None
        if subtitles_srt.strip():
            srt_path = os.path.join(work_dir, 'subtitles.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(subtitles_srt)

        final_path = os.path.join(work_dir, 'final.mp4')
        _final_pass(
            ffmpeg, concatenated, final_path,
            logo_path=local(logo_path, 'logo') if include_logo else None,
            srt_path=srt_path,
            music_path=local(music_field, 'music'),
            music_volume=music_volume,
            total_duration=total_duration,
            has_voice=any(s.voice_over_audio for s in scenes),
            width=width, height=height,
        )

        thumbnail_path = os.path.join(work_dir, 'thumbnail.jpg')
        _extract_thumbnail(ffmpeg, final_path, thumbnail_path, at_seconds=min(1.0, total_duration / 2))

        with open(final_path, 'rb') as f:
            video_bytes = f.read()
        with open(thumbnail_path, 'rb') as f:
            thumbnail_bytes = f.read()

    return video_bytes, thumbnail_bytes, total_duration, f'{width}x{height}'
