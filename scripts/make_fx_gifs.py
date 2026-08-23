import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math, os
from scipy.ndimage import label

SRC = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.png')
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'assets')
os.makedirs(OUTDIR, exist_ok=True)

img = Image.open(SRC).convert('RGB')
arr0 = np.array(img).astype(np.float32)
H, W, _ = arr0.shape
R0, G0, B0 = arr0[..., 0], arr0[..., 1], arr0[..., 2]
L0 = 0.299 * R0 + 0.587 * G0 + 0.114 * B0


def save_transparent_gif(frames_rgba, path, durations):
    """frames_rgba: list of PIL RGBA images (same size). Alpha is forced to hard 0/255
    before compositing, since GIF transparency has no partial-alpha concept."""
    w, h = frames_rgba[0].size
    bin_frames = []
    for f in frames_rgba:
        r, g, b, a = f.split()
        a_bin = a.point(lambda p: 255 if p >= 128 else 0)
        bin_frames.append(Image.merge('RGBA', (r, g, b, a_bin)))
    frames_rgba = bin_frames

    strip = Image.new('RGB', (w * len(frames_rgba), h), (255, 0, 255))
    for i, f in enumerate(frames_rgba):
        rgb = Image.new('RGB', (w, h), (255, 0, 255))
        rgb.paste(f.convert('RGB'), (0, 0), mask=f.split()[3])
        strip.paste(rgb, (i * w, 0))
    pal_img = strip.quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE)

    out_frames = []
    for f in frames_rgba:
        rgb = Image.new('RGB', (w, h), (255, 0, 255))
        alpha = f.split()[3]
        rgb.paste(f.convert('RGB'), (0, 0), mask=alpha)
        p = rgb.quantize(palette=pal_img, dither=Image.NONE)
        transparent_mask = Image.eval(alpha, lambda a: 255 if a == 0 else 0)
        p.paste(255, mask=transparent_mask)
        out_frames.append(p)

    out_frames[0].save(
        path, save_all=True, append_images=out_frames[1:],
        duration=durations, transparency=255, disposal=2,
    )


def box_mask(shape, x0, y0, x1, y1):
    m = np.zeros(shape, dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


# ================= 1. FIRE FLARE =================
fx0, fy0, fx1, fy1 = 500, 880, 760, 1150
crop_rgb = arr0[fy0:fy1, fx0:fx1].copy()
L_crop = L0[fy0:fy1, fx0:fx1]
Hc, Wc = L_crop.shape
raw_mask = L_crop > 85
labeled, n_comp = label(raw_mask)
sizes = np.bincount(labeled.ravel()); sizes[0] = 0
flame_mask = labeled == sizes.argmax()

top0 = np.full(Wc, -1, dtype=int); bottom0 = np.full(Wc, -1, dtype=int); valid = np.zeros(Wc, dtype=bool)
for x in range(Wc):
    rows = np.where(flame_mask[:, x])[0]
    if rows.size > 0:
        top0[x] = rows.min(); bottom0[x] = rows.max(); valid[x] = True
valid_cols = np.where(valid)[0]
flame_left, flame_right = valid_cols.min(), valid_cols.max()
n_bands = 6
band_of_col = np.zeros(Wc, dtype=int)
span = max(flame_right - flame_left, 1)
for x in valid_cols:
    band_of_col[x] = min(int((x - flame_left) / span * n_bands), n_bands - 1)

rng = np.random.default_rng(3)

# Sustained flicker instead of a single flare-up-and-die-down hump: each band
# gets its own smoothed random walk across the whole clip, so different flame
# licks keep moving independently for the full duration ("이글이글").
from scipy.ndimage import gaussian_filter1d

K = 32
DUR_FIRE = 110  # ms/frame -> ~3.5s of continuous blazing

band_walks = []
for b in range(n_bands):
    steps = rng.normal(0, 1.6, size=K)
    walk = np.cumsum(steps)
    walk = gaussian_filter1d(walk, sigma=1.8)
    walk -= walk.min()
    walk = walk / (walk.max() + 1e-6)  # 0..1
    band_walks.append(walk)
band_walks = np.array(band_walks)  # (n_bands, K)

MAX_GROW = 13.0
MIN_GROW = -3.0  # allow brief dips below resting height too, not just growth

fire_frames = []
for k in range(K):
    # multi-harmonic brightness flicker across the whole clip (not one hump)
    brightness = (1.0
                  + 0.13 * math.sin(0.85 * k)
                  + 0.07 * math.sin(2.05 * k + 1.0)
                  + 0.04 * math.sin(3.7 * k + 2.3))

    out_rgb = crop_rgb.copy()
    out_alpha = np.zeros((Hc, Wc), dtype=np.float32)
    out_alpha[flame_mask] = 255
    for x in valid_cols:
        t0, b0 = top0[x], bottom0[x]
        band = band_of_col[x]
        walk_val = band_walks[band, k]  # 0..1
        col_jit = ((x * 13 + k * 7) % 5 - 2) * 0.5
        grow = MIN_GROW + walk_val * (MAX_GROW - MIN_GROW) + col_jit
        new_top = max(0, min(int(round(t0 - grow)), b0 - 2))
        orig_h = b0 - t0 + 1; new_h = b0 - new_top + 1
        src = crop_rgb[t0:b0 + 1, x, :]
        src_idx = np.clip(np.round(np.linspace(0, orig_h - 1, new_h)).astype(int), 0, orig_h - 1)
        new_seg = np.clip(src[src_idx] * brightness, 0, 255)
        out_alpha[t0:b0 + 1, x] = 0
        out_rgb[new_top:new_top + new_h, x, :] = new_seg
        out_alpha[new_top:new_top + new_h, x] = 255
    rgba = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
    fire_frames.append(Image.fromarray(rgba, 'RGBA'))

save_transparent_gif(fire_frames, f'{OUTDIR}/fx-fire.gif', [DUR_FIRE] * K)
print('fire done', Wc, Hc, 'frames', K, 'duration_ms', K * DUR_FIRE)


# ================= 2. BED ZZZ =================
bx0, by0, bx1, by1 = 440, 1060, 935, 1375
Wb, Hb = bx1 - bx0, by1 - by0

def draw_pixel_z(canvas_size, scale, color):
    """Return a small RGBA image of a blocky pixel-art 'Z' at the given integer scale."""
    # 5x7 bitmap
    bitmap = [
        "11111",
        "00001",
        "00010",
        "00100",
        "01000",
        "10000",
        "11111",
    ]
    gw, gh = 5, 7
    glyph = Image.new('RGBA', (gw, gh), (0, 0, 0, 0))
    for yy, row in enumerate(bitmap):
        for xx, ch in enumerate(row):
            if ch == '1':
                glyph.putpixel((xx, yy), color)
    glyph = glyph.resize((gw * scale, gh * scale), Image.NEAREST)
    return glyph

EMBER_LIGHT = (255, 207, 138)
EMBER_DIM = (150, 100, 60)  # fade target color (still fully opaque, just dimmer) — GIF alpha is binary, so
                            # "fading" is expressed as color brightness, not partial transparency.
pillow_x, pillow_y = 830 - bx0, 1100 - by0  # local coords near the pillow

def lerp_color(c1, c2, t):
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3))

N_BED = 24
DUR_BED = 100
bed_frames = []
z_specs = [
    dict(start=0,  life=14, scale=2, dx=10, dy=-46, x0=pillow_x - 4,  y0=pillow_y - 6),
    dict(start=6,  life=14, scale=3, dx=16, dy=-54, x0=pillow_x + 8,  y0=pillow_y - 2),
    dict(start=12, life=14, scale=4, dx=22, dy=-60, x0=pillow_x + 22, y0=pillow_y + 4),
]

for k in range(N_BED):
    canvas = Image.new('RGBA', (Wb, Hb), (0, 0, 0, 0))
    for spec in z_specs:
        local_k = k - spec['start']
        if 0 <= local_k < spec['life']:
            t = local_k / (spec['life'] - 1)
            if t > 0.82:  # vanish on the last couple of steps instead of fading alpha
                continue
            fade_t = min(t / 0.7, 1.0)  # color dims over the first 70% of its life, then holds until it vanishes
            color = lerp_color(EMBER_LIGHT, EMBER_DIM, fade_t) + (255,)
            glyph = draw_pixel_z(None, spec['scale'], color)
            px = int(round(spec['x0'] + spec['dx'] * t))
            py = int(round(spec['y0'] + spec['dy'] * t))
            canvas.alpha_composite(glyph, (px, py))
    bed_frames.append(canvas)

save_transparent_gif(bed_frames, f'{OUTDIR}/fx-bed.gif', [DUR_BED] * N_BED)
print('bed done', Wb, Hb)

# ================= 3. NIGHT SHOOTING STAR =================
nx0, ny0, nx1, ny1 = 20, 380, 385, 955
Wn, Hn = nx1 - nx0, ny1 - ny0
start_local = (50, 50)
end_local = (325, 280)

N_STAR = 16
DUR_STAR = 80
TRAIL = 4
STAR_WHITE = (255, 255, 255)
STAR_DIM = (70, 90, 130)  # dims toward the night sky's own blue rather than fading alpha
star_frames = []
for k in range(N_STAR):
    canvas = Image.new('RGBA', (Wn, Hn), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for trail_i in range(TRAIL + 1):
        kk = k - trail_i
        if kk < 0 or kk >= N_STAR - 3:
            continue
        t = kk / (N_STAR - 4)
        if t > 1:
            continue
        px = start_local[0] + (end_local[0] - start_local[0]) * t
        py = start_local[1] + (end_local[1] - start_local[1]) * t
        dim_t = trail_i / TRAIL
        color = lerp_color(STAR_WHITE, STAR_DIM, dim_t)
        size = 2 if trail_i == 0 else 1
        draw.rectangle([px - size, py - size, px + size, py + size], fill=color + (255,))
    star_frames.append(canvas)

save_transparent_gif(star_frames, f'{OUTDIR}/fx-star.gif', [DUR_STAR] * N_STAR)
print('star done', Wn, Hn)

# ================= 4. PUDDLE RIPPLE =================
px0, py0, px1, py1 = 100, 1250, 430, 1600
Wp, Hp = px1 - px0, py1 - py0
center_local = (160, 170)

N_RIP = 20
DUR_RIP = 90
ring_specs = [dict(start=0, life=14), dict(start=6, life=14), dict(start=12, life=14)]
RING_BRIGHT = (214, 232, 255)
RING_DIM = (40, 55, 80)  # ring dims toward the puddle's own dark water tone rather than fading alpha

ripple_frames = []
for k in range(N_RIP):
    canvas = Image.new('RGBA', (Wp, Hp), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for spec in ring_specs:
        local_k = k - spec['start']
        if 0 <= local_k < spec['life']:
            t = local_k / (spec['life'] - 1)
            if t > 0.88:
                continue
            radius = 3 + t * 60
            color = lerp_color(RING_BRIGHT, RING_DIM, min(t / 0.75, 1.0))
            bbox = [center_local[0] - radius, center_local[1] - radius * 0.42,
                    center_local[0] + radius, center_local[1] + radius * 0.42]
            draw.ellipse(bbox, outline=color + (255,), width=1)
    ripple_frames.append(canvas)

save_transparent_gif(ripple_frames, f'{OUTDIR}/fx-puddle.gif', [DUR_RIP] * N_RIP)
print('puddle done', Wp, Hp)

print('\nBBOX PERCENTAGES (of', W, 'x', H, ')')
for name, (x0, y0, x1, y1) in [
    ('fire', (fx0, fy0, fx1, fy1)),
    ('bed', (bx0, by0, bx1, by1)),
    ('night', (nx0, ny0, nx1, ny1)),
    ('puddle', (px0, py0, px1, py1)),
]:
    print(name, dict(left=round(x0/W*100,3), top=round(y0/H*100,3), width=round((x1-x0)/W*100,3), height=round((y1-y0)/H*100,3)))
