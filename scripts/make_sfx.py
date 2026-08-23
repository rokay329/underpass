import numpy as np
from scipy import signal
import wave, os

SR = 44100
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sfx')
os.makedirs(OUTDIR, exist_ok=True)

rng = np.random.default_rng(11)


def save_wav(path, mono, sr=SR):
    mono = np.clip(mono, -1, 1)
    stereo = np.stack([mono, mono], axis=-1)
    audio_i16 = (stereo * 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_i16.tobytes())


def env_ad(n, attack, decay_power=2.2):
    """Fast attack, exponential-ish decay over the full buffer."""
    t = np.linspace(0, 1, n)
    a = min(max(attack, 1), n)
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a)
    tail = np.linspace(0, 1, n)
    env *= np.exp(-tail * decay_power * 4)
    return env


def filtered_noise(n, low, high, sr=SR):
    x = rng.normal(0, 1, n)
    sos = signal.butter(2, [low, high], btype='bandpass', fs=sr, output='sos')
    return signal.sosfilt(sos, x)


# ---------------- fire: crackling whoosh ----------------
def make_fire():
    dur = 0.6
    n = int(SR * dur)
    body = filtered_noise(n, 250, 2800)
    env = env_ad(n, attack=int(SR * 0.01), decay_power=3.0)
    out = body * env

    # a few sharp ember pops layered in
    for _ in range(5):
        p = rng.integers(0, int(n * 0.7))
        length = rng.integers(80, 220)
        if p + length >= n:
            continue
        pop_env = np.exp(-np.linspace(0, 10, length))
        pop = rng.normal(0, 1, length) * pop_env
        sos = signal.butter(2, [900, 5000], btype='bandpass', fs=SR, output='sos')
        pop = signal.sosfilt(sos, pop)
        out[p:p + length] += pop * 0.5

    out /= np.max(np.abs(out)) + 1e-9
    save_wav(f'{OUTDIR}/fire.wav', out * 0.5)


# ---------------- bed: soft breath / rustle ----------------
def make_bed():
    dur = 0.9
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    body = filtered_noise(n, 150, 1400)
    # gentle rise-fall breath envelope
    env = np.sin(np.pi * (t / dur)) ** 1.6
    out = body * env
    out /= np.max(np.abs(out)) + 1e-9
    save_wav(f'{OUTDIR}/bed.wav', out * 0.35)


# ---------------- night: sparkly chime ----------------
def make_night():
    dur = 1.0
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    f0 = 1500
    vibrato = 1 + 0.004 * np.sin(2 * np.pi * 7 * t)
    tone = np.sin(2 * np.pi * f0 * vibrato * t)
    tone += 0.35 * np.sin(2 * np.pi * f0 * 2.01 * vibrato * t)
    tone += 0.15 * np.sin(2 * np.pi * f0 * 3.0 * vibrato * t)
    env = np.exp(-t * 5.5)
    env[: int(SR * 0.004)] *= np.linspace(0, 1, int(SR * 0.004))
    out = tone * env
    out /= np.max(np.abs(out)) + 1e-9
    save_wav(f'{OUTDIR}/night.wav', out * 0.3)


# ---------------- puddle: water drop plink + faint echo ----------------
def make_puddle():
    dur = 0.55
    n = int(SR * dur)
    t = np.linspace(0, dur, n)

    def ping(t, f_start, f_end, decay):
        freq = f_end + (f_start - f_end) * np.exp(-t * 22)
        phase = 2 * np.pi * np.cumsum(freq) / SR
        env = np.exp(-t * decay)
        env[: int(SR * 0.002)] *= np.linspace(0, 1, int(SR * 0.002))
        return np.sin(phase) * env

    out = ping(t, 900, 480, 10)
    delay = int(SR * 0.11)
    echo = np.zeros(n)
    echo_sig = ping(t, 750, 400, 10) * 0.45
    echo[delay:] += echo_sig[: n - delay]
    out = out + echo
    out /= np.max(np.abs(out)) + 1e-9
    save_wav(f'{OUTDIR}/puddle.wav', out * 0.32)


# ---------------- lantern: puff out ... catch back alight ----------------
def make_lantern():
    dur = 1.5
    n = int(SR * dur)
    out = np.zeros(n)

    # puff (blow-out breath)
    puff_n = int(SR * 0.35)
    puff = filtered_noise(puff_n, 150, 1100)
    puff_env = env_ad(puff_n, attack=int(SR * 0.02), decay_power=3.5)
    out[:puff_n] += puff * puff_env * 0.8

    # pause, then a tiny spark/catch tick
    catch_start = int(SR * 0.75)
    tick_n = 400
    tick = rng.normal(0, 1, tick_n) * np.exp(-np.linspace(0, 14, tick_n))
    sos = signal.butter(2, [1500, 6000], btype='bandpass', fs=SR, output='sos')
    tick = signal.sosfilt(sos, tick)
    out[catch_start:catch_start + tick_n] += tick * 0.5

    # soft warm relight swell (low tone fading in/out)
    swell_start = catch_start + int(SR * 0.05)
    swell_n = n - swell_start
    ts = np.linspace(0, 1, swell_n)
    swell = filtered_noise(swell_n, 200, 900) * (np.sin(np.pi * ts) ** 1.3)
    out[swell_start:] += swell * 0.3

    out /= np.max(np.abs(out)) + 1e-9
    save_wav(f'{OUTDIR}/lantern.wav', out * 0.42)


# ---------------- tarp: low wind whoosh ----------------
def make_tarp():
    dur = 1.3
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    body = filtered_noise(n, 120, 1000)
    env = np.sin(np.pi * (t / dur)) ** 1.2
    out = body * env
    out /= np.max(np.abs(out)) + 1e-9
    save_wav(f'{OUTDIR}/tarp.wav', out * 0.4)


make_fire()
make_bed()
make_night()
make_puddle()
make_lantern()
make_tarp()
print('all sfx written to', OUTDIR)
for f in sorted(os.listdir(OUTDIR)):
    print(' -', f)
