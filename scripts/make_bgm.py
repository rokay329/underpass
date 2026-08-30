import numpy as np
from scipy import signal
import os

SR = 44100
OUT_WAV = os.path.join(os.path.dirname(__file__), '..', 'assets', 'bgm.wav')

rng = np.random.default_rng(7)

# ---------------- chord pad ----------------
# Am7 - Fmaj7 - Cmaj7 - G7, warm/melancholic, slow (4s per chord, 16s loop)
CHORD_DUR = 4.0
CHORDS = [
    ([220.00, 261.63, 329.63, 392.00], 110.00),   # Am7  + A2 bass
    ([174.61, 220.00, 261.63, 329.63], 87.31),    # Fmaj7 + F2 bass
    ([130.81, 164.81, 196.00, 246.94], 65.41),    # Cmaj7 + C2 bass
    ([196.00, 246.94, 293.66, 349.23], 98.00),    # G7    + G2 bass
]

def triangle(freq, t, detune_cents=0.0):
    f = freq * (2 ** (detune_cents / 1200))
    return signal.sawtooth(2 * np.pi * f * t, width=0.5)

def synth_chord(freqs, bass_freq, duration, sr):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = np.zeros_like(t)
    for f in freqs:
        for detune in (-6, 6):  # cents, gentle chorus-like warmth
            wave += triangle(f, t, detune)
    wave /= (len(freqs) * 2)

    bass = 0.55 * np.sin(2 * np.pi * bass_freq * t)
    bass += 0.15 * np.sin(2 * np.pi * bass_freq * 2 * t)  # a little octave harmonic for body

    env = np.ones_like(t)
    fade = int(sr * 0.9)
    env[:fade] *= np.linspace(0, 1, fade) ** 1.5
    env[-fade:] *= np.linspace(1, 0, fade) ** 1.5

    return (wave * 0.5 + bass * 0.5) * env

pad = np.concatenate([synth_chord(freqs, bass, CHORD_DUR, SR) for freqs, bass in CHORDS])

# gentle overall amplitude breathing so the pad isn't perfectly static
n = len(pad)
t_full = np.arange(n) / SR
breathe = 1.0 + 0.06 * np.sin(2 * np.pi * t_full / 8.0)
pad *= breathe
pad *= 0.16  # pad level

# ---------------- vinyl hiss (continuous, very quiet) ----------------
hiss = rng.normal(0, 1, n)
sos_hp = signal.butter(2, 800, btype='highpass', fs=SR, output='sos')
hiss = signal.sosfilt(sos_hp, hiss)
sos_lp = signal.butter(2, 9000, btype='lowpass', fs=SR, output='sos')
hiss = signal.sosfilt(sos_lp, hiss)
hiss = hiss / np.max(np.abs(hiss)) * 0.018

# ---------------- vinyl crackle (sparse pops) ----------------
crackle = np.zeros(n)
n_pops = int(n / SR * 4.5)  # ~4.5 pops/sec on average
pop_positions = rng.integers(0, n, size=n_pops)
for p in pop_positions:
    length = rng.integers(20, 90)
    if p + length >= n:
        continue
    decay = np.exp(-np.linspace(0, 12, length))
    click = rng.normal(0, 1, length) * decay
    amp = rng.uniform(0.03, 0.10)
    crackle[p:p + length] += click * amp

sos_crackle = signal.butter(2, [1200, 11000], btype='bandpass', fs=SR, output='sos')
crackle = signal.sosfilt(sos_crackle, crackle)

# ---------------- mix ----------------
mix = pad + hiss + crackle

# gentle overall lowpass for a soft, muffled "tape" warmth
sos_master = signal.butter(2, 7500, btype='lowpass', fs=SR, output='sos')
mix = signal.sosfilt(sos_master, mix)

# make the loop point seamless: crossfade the very end back into the very start
xf = int(SR * 0.35)
head = mix[:xf].copy()
tail = mix[-xf:].copy()
fade_in = np.linspace(0, 1, xf)
fade_out = 1 - fade_in
mix[-xf:] = tail * fade_out + head * fade_in

# subtle fade-in/out right at the loop boundary itself (on top of the
# crossfade above): the crossfade blends the *musical* content so nothing
# clips or lurches at the seam, but its two ends still don't land on
# exactly the same sample value, so <audio loop> can still leave the
# faintest click at the wrap. Ducking both edges down to true silence
# over a short window removes that possibility outright -- silence
# meeting silence is seamless no matter what.
edge_fade_n = int(SR * 0.15)
edge_in = np.linspace(0, 1, edge_fade_n) ** 1.5
edge_out = np.linspace(1, 0, edge_fade_n) ** 1.5
mix[:edge_fade_n] *= edge_in
mix[-edge_fade_n:] *= edge_out

# normalize to a gentle, background-appropriate level (well below clipping)
peak = np.max(np.abs(mix))
mix = mix / peak * 0.5

stereo = np.stack([mix, mix], axis=-1)
# tiny stereo width via a few-ms delay on one channel (subtle, avoids mono-flatness)
delay_samples = int(SR * 0.006)
right = np.concatenate([np.zeros(delay_samples), mix[:-delay_samples]])
stereo = np.stack([mix, right], axis=-1)

audio_i16 = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)

import wave
with wave.open(OUT_WAV, 'wb') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(audio_i16.tobytes())

print('saved', OUT_WAV, 'duration', n / SR, 's')
