"""A built-in background music bed, used when "Background music" is on but the Music Library has no tracks.

Synthesised here (pure Python, no samples, so nothing to license): a soft, warm pad over a I-V-vi-IV chord
progression with a gentle bass and a quiet bell arpeggio - the unobtrusive "corporate ambient" bed that sits
under a voice-over without competing with it. One 16-second loop is written as a WAV; rendering.py loops it
under the whole video, mixes it low under the voice and fades it out at the end.
"""

import math
import random
import struct
import wave

SAMPLE_RATE = 22050
BEATS_PER_CHORD = 4
BPM = 60  # one beat a second - calm, and the loop is 4 chords x 4 beats = 16 seconds

# Root notes (Hz) of a few warm major keys; the bed picks one per video so videos don't all sound the same.
KEYS = {'C': 261.63, 'D': 293.66, 'Eb': 311.13, 'F': 349.23, 'G': 392.00}
# I - V - vi - IV, as semitone offsets of each chord's triad from the key's root.
PROGRESSION = ((0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12))
ARPEGGIO = (0, 1, 2, 1, 0, 2, 1, 2)  # triad note index for each eighth note


def _note(root, semitones):
    return root * 2 ** (semitones / 12)


def write_music_bed(path, *, seed=None):
    """Writes the loop to `path` (16-bit mono WAV). Returns the loop length in seconds."""
    rng = random.Random(seed)
    root = KEYS[rng.choice(sorted(KEYS))] / 2  # one octave down: a pad, not a melody
    chord_seconds = BEATS_PER_CHORD * 60 / BPM
    loop_seconds = chord_seconds * len(PROGRESSION)
    total = int(loop_seconds * SAMPLE_RATE)
    chord_len = int(chord_seconds * SAMPLE_RATE)
    eighth = chord_len // (BEATS_PER_CHORD * 2)
    tau = 2 * math.pi
    samples = []
    for i in range(total):
        t = i / SAMPLE_RATE
        index = i // chord_len
        chord = PROGRESSION[index % len(PROGRESSION)]
        within = (i - index * chord_len) / chord_len
        # The pad swells in and out on each chord, so chords cross-fade instead of cutting.
        swell = math.sin(math.pi * within) ** 0.6
        pad = 0.0
        for semitones in chord:
            frequency = _note(root, semitones)
            pad += math.sin(tau * frequency * t) + 0.5 * math.sin(tau * frequency * 1.003 * t)  # gentle chorus
        pad *= swell / (len(chord) * 1.5)
        bass = 0.55 * swell * math.sin(tau * _note(root / 2, chord[0]) * t)
        # A soft bell on each eighth note: a high sine with a fast exponential decay.
        step = (i - index * chord_len) // eighth
        since = ((i - index * chord_len) % eighth) / SAMPLE_RATE
        bell_frequency = _note(root * 4, chord[ARPEGGIO[step % len(ARPEGGIO)]])
        bell = 0.22 * math.exp(-since * 5.0) * math.sin(tau * bell_frequency * t)
        samples.append(0.42 * pad + 0.25 * bass + bell)

    # Fade the loop's ends a little so the repeat point is seamless.
    edge = int(0.05 * SAMPLE_RATE)
    for k in range(edge):
        gain = k / edge
        samples[k] *= gain
        samples[-1 - k] *= gain
    peak = max(abs(value) for value in samples) or 1.0
    frames = b''.join(struct.pack('<h', int(32000 * 0.8 * value / peak)) for value in samples)
    with wave.open(path, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(frames)
    return loop_seconds
