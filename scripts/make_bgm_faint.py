import numpy as np
from scipy import signal
import wave
import os

SR = 44100
OUT_WAV = os.path.join(os.path.dirname(__file__), 'bgm-faint.wav')

rng = np.random.default_rng(41)

# ---------------- chord pad ----------------
# Same chord world as the cozy variant (scripts/make_bgm_cozy.py) --
# Am9 - Fmaj9 - Cmaj9 - Gm9 -- so all three BGM options feel like the
# same piece heard at different distances/energies, not unrelated
# tracks. Held even longer here (8s/chord vs cozy's 6s) so the harmony
# is closer to a still drone than a "progression".
CHORD_DUR = 8.0
CHORDS = [
    ([110.00, 130.81, 164.81, 196.00, 246.94], 55.00),   # Am9   + A1 bass
    ([87.31,  110.00, 130.81, 164.81, 196.00], 43.65),   # Fmaj9 + F1 bass
    ([65.41,  82.41,  98.00,  123.47, 164.81], 32.70),   # Cmaj9 + C1 bass
    ([98.00,  116.54, 146.83, 174.61, 220.00], 49.00),   # Gm9   + G1 bass
]

def synth_chord(freqs, bass_freq, duration, sr, t_offset=0.0):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    t_abs = t + t_offset

    # slower, slightly deeper wobble than the cozy version -- this is
    # the faintest/farthest-away of the three, so it should feel like
    # it's drifting a little further from true pitch, not just held.
    wow = 1.0 + 0.003 * np.sin(2 * np.pi * 0.08 * t_abs + 0.4)

    wave_out = np.zeros_like(t)
    for f in freqs:
        for detune in (-4, 4):
            fi = f * (2 ** (detune / 1200)) * wow
            phase = 2 * np.pi * np.cumsum(fi) / sr
            wave_out += np.sin(phase) + 0.08 * np.sin(2 * phase)
    wave_out /= (len(freqs) * 2)

    bass_fi = bass_freq * wow
    bass_phase = 2 * np.pi * np.cumsum(bass_fi) / sr
    bass = 0.55 * np.sin(bass_phase)
    bass += 0.10 * np.sin(2 * bass_phase)

    # very long, soft attack/release, most of the chord is the
    # sustained middle -- almost nothing "happens", it just is there.
    env = np.ones_like(t)
    fade = int(sr * 2.6)
    env[:fade] *= np.linspace(0, 1, fade) ** 2.2
    env[-fade:] *= np.linspace(1, 0, fade) ** 2.2

    return (wave_out * 0.55 + bass * 0.45) * env

pad_parts = [
    synth_chord(freqs, bass, CHORD_DUR, SR, t_offset=i * CHORD_DUR)
    for i, (freqs, bass) in enumerate(CHORDS)
]
pad = np.concatenate(pad_parts)
n = len(pad)
t_full = np.arange(n) / SR

# very slow, shallow breathing -- barely perceptible, just enough that
# it doesn't feel frozen
breathe = 1.0 + 0.035 * np.sin(2 * np.pi * t_full / 20.0)
pad *= breathe

def sweeping_lowpass(x, sr, base_cutoff, depth, period):
    block = int(sr * 0.25)
    hop = block // 2
    out = np.zeros_like(x)
    win = np.hanning(block)
    norm = np.zeros_like(x)
    i = 0
    while i < len(x):
        seg = x[i:i + block]
        if len(seg) < block:
            seg = np.pad(seg, (0, block - len(seg)))
        t_center = (i + block / 2) / sr
        cutoff = base_cutoff + depth * np.sin(2 * np.pi * t_center / period)
        cutoff = float(np.clip(cutoff, 350, sr / 2 - 100))
        sos = signal.butter(2, cutoff, btype='lowpass', fs=sr, output='sos')
        filtered = signal.sosfilt(sos, seg) * win
        end = min(i + block, len(x))
        out[i:end] += filtered[:end - i]
        norm[i:end] += win[:end - i]
        i += hop
    norm[norm == 0] = 1.0
    return out / norm

# lower + slower sweep than the cozy version -- sits further under a
# blanket, and takes longer to (barely) resurface
pad = sweeping_lowpass(pad, SR, base_cutoff=1300, depth=450, period=24.0)
pad *= 0.13  # quieter pad level than cozy (0.20) -- this is the faint one

# ---------------- continuous soft wind bed ----------------
# broadband noise, bandpassed to a breathy mid-range, with two slow
# offset sine gusts multiplied together so the swells feel irregular
# (a real gust, not a metronomic pulse) rather than a single smooth LFO.
wind_noise = rng.normal(0, 1, n)
sos_wind = signal.butter(2, [180, 1500], btype='bandpass', fs=SR, output='sos')
wind = signal.sosfilt(sos_wind, wind_noise)
wind = wind / (np.max(np.abs(wind)) + 1e-9)
gust_a = 0.5 + 0.5 * np.sin(2 * np.pi * t_full / 11.0 + 0.3)
gust_b = 0.5 + 0.5 * np.sin(2 * np.pi * t_full / 17.5 + 2.1)
gust = 0.35 + 0.65 * (gust_a * gust_b)
wind = wind * gust
wind *= 0.045

# (an earlier version also scattered a few synthesized water-drip pings
# through the loop, reusing the puddle-sfx "ping" technique from
# scripts/make_sfx.py -- removed per feedback so this track is just the
# pad + wind, nothing else mixed in.)

# ---------------- mix ----------------
mix = pad + wind

# heaviest lowpass of the three tracks -- the faintest, most distant one
sos_master = signal.butter(2, 3200, btype='lowpass', fs=SR, output='sos')
mix = signal.sosfilt(sos_master, mix)

# seamless loop point
xf = int(SR * 1.0)
head = mix[:xf].copy()
tail = mix[-xf:].copy()
fade_in = np.linspace(0, 1, xf)
fade_out = 1 - fade_in
mix[-xf:] = tail * fade_out + head * fade_in

# subtle fade-in/out right at the loop boundary itself (on top of the
# crossfade above) -- ducks both edges down to true silence over a short
# window so <audio loop> wraps silence-to-silence, with no possibility of
# a residual click where the crossfaded tail and the untouched head don't
# quite land on the same sample value.
edge_fade_n = int(SR * 0.35)
edge_in = np.linspace(0, 1, edge_fade_n) ** 1.5
edge_out = np.linspace(1, 0, edge_fade_n) ** 1.5
mix[:edge_fade_n] *= edge_in
mix[-edge_fade_n:] *= edge_out

peak = np.max(np.abs(mix))
mix = mix / peak * 0.34  # noticeably quieter than the cozy track's 0.46

stereo_delay = int(SR * 0.011)
right = np.concatenate([np.zeros(stereo_delay), mix[:-stereo_delay]])
stereo = np.stack([mix, right], axis=-1)

audio_i16 = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)

with wave.open(OUT_WAV, 'wb') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(audio_i16.tobytes())

print('saved', OUT_WAV, 'duration', n / SR, 's')
