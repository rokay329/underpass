import numpy as np
import wave, os

SR = 44100
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sfx')
OUTDIR = os.environ.get("OUTDIR", OUTDIR)
os.makedirs(OUTDIR, exist_ok=True)


def save_wav(path, mono, sr=SR):
    mono = np.clip(mono, -1, 1)
    stereo = np.stack([mono, mono], axis=-1)
    audio_i16 = (stereo * 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_i16.tobytes())


def note_env(n, attack, release):
    """Soft raised-cosine attack, long soft release — no hard onset."""
    env = np.ones(n)
    a = min(max(int(attack), 1), n)
    r = min(max(int(release), 1), n)
    env[:a] = 0.5 * (1 - np.cos(np.pi * np.arange(a) / a))
    tail = np.arange(r)
    rel_curve = 0.5 * (1 + np.cos(np.pi * tail / r))
    env[n - r:] = np.minimum(env[n - r:], rel_curve)
    return env


def tone(freq, dur, sr=SR, warmth=0.28, vibrato_rate=3.4, vibrato_depth=0.0025):
    n = int(sr * dur)
    t = np.arange(n) / sr
    vibrato = 1 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    fundamental = np.sin(2 * np.pi * freq * vibrato * t)
    # a soft second + third partial, quieter, for a warm (not thin) low tone
    partial2 = warmth * 0.5 * np.sin(2 * np.pi * freq * 2 * vibrato * t)
    partial3 = warmth * 0.22 * np.sin(2 * np.pi * freq * 3 * vibrato * t)
    sub = 0.35 * np.sin(2 * np.pi * freq * 0.5 * vibrato * t)  # one octave below, quiet
    out = fundamental + partial2 + partial3 + sub
    out *= note_env(n, attack=sr * 0.09, release=sr * 0.72)
    return out


def make_intro():
    # low, relaxed, unhurried 4-note phrase that settles rather than resolves
    # upward — drifts down at the end like a slow exhale.
    notes = [
        (110.00, 0.00, 0.95),  # A2
        (130.81, 0.46, 0.95),  # C3
        (164.81, 0.95, 1.05),  # E3
        (146.83, 1.55, 1.30),  # D3 (settles here)
    ]
    total = max(start + dur for _, start, dur in notes) + 0.6
    n_total = int(SR * total)
    out = np.zeros(n_total)

    for freq, start, dur in notes:
        seg = tone(freq, dur)
        s = int(SR * start)
        e = s + len(seg)
        if e > len(out):
            seg = seg[: len(out) - s]
            e = len(out)
        out[s:e] += seg * 0.5

    # soft slap-back echo for a relaxed, spacious feel
    delay_samples = int(SR * 0.24)
    echo = np.zeros_like(out)
    echo[delay_samples:] = out[:-delay_samples] * 0.28
    out = out + echo

    # master fade in/out so the clip has no abrupt edges
    fade_in = int(SR * 0.05)
    fade_out = int(SR * 0.55)
    out[:fade_in] *= np.linspace(0, 1, fade_in)
    out[-fade_out:] *= np.linspace(1, 0, fade_out)

    out /= (np.max(np.abs(out)) + 1e-9)
    out *= 0.72  # keep it gentle, not a loud sting
    return out


if __name__ == "__main__":
    audio = make_intro()
    path = os.path.join(OUTDIR, "intro.wav")
    save_wav(path, audio)
    print("wrote", path, f"{len(audio) / SR:.2f}s")
