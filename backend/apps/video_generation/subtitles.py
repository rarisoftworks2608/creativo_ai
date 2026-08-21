"""Pure-local SRT subtitle generation from a scene timeline (Epic 07: Subtitles).

No external API is needed - the subtitle track is just each scene's
narration, timestamped by accumulating scene durations in order.
"""


def _format_timestamp(seconds):
    total_ms = int(max(seconds, 0) * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}'


def build_srt(scenes):
    """scenes: an iterable of objects with .narration and .duration_seconds, in scene order."""
    lines = []
    cursor = 0.0
    counter = 0
    for scene in scenes:
        start = cursor
        end = cursor + scene.duration_seconds
        if scene.narration.strip():
            counter += 1
            lines.append(str(counter))
            lines.append(f'{_format_timestamp(start)} --> {_format_timestamp(end)}')
            lines.append(scene.narration.strip())
            lines.append('')
        cursor = end
    return '\n'.join(lines)
