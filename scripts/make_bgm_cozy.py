import numpy as np
from scipy import signal
import wave
import os

SR = 44100
OUT_WAV = os.path.join(os.path.dirname(__file__), 'bgm-cozy.wav')

rng = np.random.default_rng(23)

# ---------------- chord pad ----------------
# Same warm progression as the original (Am9 - Fmaj9 - Cmaj9 - Gm9-ish),
# but with 9ths added for extra dreaminess, voiced an octave lower, and
# held much longer per chord (6s vs 4s) so the harmony barely seems to
# move -- the core of the "drowsy" feel.
CHORD_DUR = 6.0
CHORDS = [
    ([110.00, 130.81, 164.81, 196.00, 246.94], 55.00),   # Am9   + A1 bass
    ([87.31,  110.00, 130.81, 164.81, 196.00], 43.65),   # Fmaj9 + F1 bass
    ([65.41,  82.41,  98.00,  123.47, 164.81], 32.70),   # Cmaj9 + C1 bass
    ([98.00,  116.54, 146.83, 174.61, 220.00], 49.00),   # Gm9   + G1 bass
]

def synth_chord(freqs, bass_freq, duration, sr, t_offset=0.0):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    t_abs = t + t_offset

    # slow "wow" pitch wobble -- a lazy, half-asleep tape sway rather than
    # a steady pitch. ~0.11Hz (about one sway every 9s), tiny depth.
    wow = 1.0 + 0.0022 * np.sin(2 * np.pi * 0.11 * t_abs + 0.7)

    wave_out = np.zeros_like(t)
    for f in freqs:
        for detune in (-5, 5):  # cents, soft chorus width
            fi = f * (2 ** (detune / 1200)) * wow
            phase = 2 * np.pi * np.cumsum(fi) / sr
            # pure-ish sine core plus a whisper of 2nd harmonic for body,
            # instead of the brighter sawtooth/triangle used in the
            # original -- rounder, breathier, less "bite".
            wave_out += np.sin(phase) + 0.10 * np.sin(2 * phase)
    wave_out /= (len(freqs) * 2)

    bass_fi = bass_freq * wow
    bass_phase = 2 * np.pi * np.cumsum(bass_fi) / sr
    bass = 0.6 * np.sin(bass_phase)
    bass += 0.12 * np.sin(2 * bass_phase)

    # long, soft attack/release -- nothing about this pad should ever
    # feel like it "arrives"; it should just gradually be there, like
    # drifting into a doze.
    env = np.ones_like(t)
    fade = int(sr * 1.8)
    env[:fade] *= np.linspace(0, 1, fade) ** 2.0
    env[-fade:] *= np.linspace(1, 0, fade) ** 2.0

    return (wave_out * 0.55 + bass * 0.45) * env

n_per_chord = int(SR * CHORD_DUR)
pad_parts = []
for i, (freqs, bass) in enumerate(CHORDS):
    pad_parts.append(synth_chord(freqs, bass, CHORD_DUR, SR, t_offset=i * CHORD_DUR))
pad = np.concatenate(pad_parts)
n = len(pad)
t_full = np.arange(n) / SR

# slow amplitude breathing, longer period than the original (14s vs 8s)
# so it reads as slow, sleepy breathing rather than a pulse
breathe = 1.0 + 0.05 * np.sin(2 * np.pi * t_full / 14.0)
pad *= breathe

# slow lowpass-cutoff "breathing blanket" sweep: filter the whole pad
# through a cutoff that gently rises and falls, so it periodically
# muffles further under the covers and then eases back -- classic
# cozy lo-fi filter-sweep texture. Implemented by filtering in short
# overlapping blocks with a slowly varying cutoff.
def sweeping_lowpass(x, sr, base_cutoff=1800, depth=650, period=18.0):
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
        cutoff = float(np.clip(cutoff, 400, sr / 2 - 100))
        sos = signal.butter(2, cutoff, btype='lowpass', fs=sr, output='sos')
        filtered = signal.sosfilt(sos, seg) * win
        end = min(i + block, len(x))
        out[i:end] += filtered[:end - i]
        norm[i:end] += win[:end - i]
        i += hop
    norm[norm == 0] = 1.0
    return out / norm

pad = sweeping_lowpass(pad, SR)
pad *= 0.20  # pad level

# ---------------- vinyl hiss (continuous, very quiet) ----------------
hiss = rng.normal(0, 1, n)
sos_hp = signal.butter(2, 700, btype='highpass', fs=SR, output='sos')
hiss = signal.sosfilt(sos_hp, hiss)
sos_lp = signal.butter(2, 5500, btype='lowpass', fs=SR, output='sos')
hiss = signal.sosfilt(sos_lp, hiss)
hiss = hiss / np.max(np.abs(hiss)) * 0.014

# ---------------- vinyl crackle (sparser, gentler than the original) ----------------
crackle = np.zeros(n)
n_pops = int(n / SR * 2.0)  # ~2 pops/sec, calmer than the original 4.5/sec
pop_positions = rng.integers(0, n, size=n_pops)
for p in pop_positions:
    length = rng.integers(25, 100)
    if p + length >= n:
        continue
    decay = np.exp(-np.linspace(0, 13, length))
    click = rng.normal(0, 1, length) * decay
    amp = rng.uniform(0.02, 0.06)
    crackle[p:p + length] += click * amp

sos_crackle = signal.butter(2, [1000, 8000], btype='bandpass', fs=SR, output='sos')
crackle = signal.sosfilt(sos_crackle, crackle)

# ---------------- gentle low room hum (radiator/heater-ish, very soft) ----------------
hum_noise = rng.normal(0, 1, n)
sos_hum = signal.butter(2, [70, 220], btype='bandpass', fs=SR, output='sos')
hum = signal.sosfilt(sos_hum, hum_noise)
hum = hum / np.max(np.abs(hum)) * 0.02
hum *= 1.0 + 0.15 * np.sin(2 * np.pi * t_full / 21.0)  # very slow swell

# ---------------- mix ----------------
mix = pad + hiss + crackle + hum

# soft overall lowpass -- muffled, blanket warmth, more so than the
# original (3800Hz here vs 7500Hz there)
sos_master = signal.butter(2, 3800, btype='lowpass', fs=SR, output='sos')
mix = signal.sosfilt(sos_master, mix)

# seamless loop point
xf = int(SR * 0.6)
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
edge_fade_n = int(SR * 0.25)
edge_in = np.linspace(0, 1, edge_fade_n) ** 1.5
edge_out = np.linspace(1, 0, edge_fade_n) ** 1.5
mix[:edge_fade_n] *= edge_in
mix[-edge_fade_n:] *= edge_out

peak = np.max(np.abs(mix))
mix = mix / peak * 0.46  # a touch quieter/gentler than the original's 0.5

stereo_delay = int(SR * 0.009)
right = np.concatenate([np.zeros(stereo_delay), mix[:-stereo_delay]])
stereo = np.stack([mix, right], axis=-1)

audio_i16 = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)

with wave.open(OUT_WAV, 'wb') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(audio_i16.tobytes())

print('saved', OUT_WAV, 'duration', n / SR, 's')
