import numpy as np
from PIL import Image, ImageDraw
import math, os
from scipy.ndimage import distance_transform_edt

SRC = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.png')
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'assets')

img = Image.open(SRC).convert('RGB')
arr0 = np.array(img).astype(np.float32)
H, W, _ = arr0.shape
R0, G0, B0 = arr0[..., 0], arr0[..., 1], arr0[..., 2]
L0 = 0.299 * R0 + 0.587 * G0 + 0.114 * B0


def save_transparent_gif(frames_rgba, path, durations):
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


# ================= LANTERN: pendulum swing (damped) + flame flicker =================
lx0, ly0, lx1, ly1 = 545, 680, 650, 815
Lc = arr0[ly0:ly1, lx0:lx1].copy()
Hc, Wc, _ = Lc.shape
Lc_lum = L0[ly0:ly1, lx0:lx1]

# geometric mask: chain (thin strip) + lantern body (blob), in LOCAL crop coords
mask = np.zeros((Hc, Wc), dtype=bool)
chain_x0, chain_x1 = 592 - lx0, 600 - lx0
chain_y0, chain_y1 = 685 - ly0, 745 - ly0
mask[chain_y0:chain_y1, chain_x0:chain_x1] = True
body_x0, body_x1 = 570 - lx0, 620 - lx0
body_y0, body_y1 = 745 - ly0, 803 - ly0
mask[body_y0:body_y1, body_x0:body_x1] = True

idx = distance_transform_edt(mask, return_distances=False, return_indices=True)
bg_fill = Lc[idx[0], idx[1]]

pivot_row = 0  # top of crop = mount point, zero swing there
bottom_row = body_y1

flame_local_mask = np.zeros((Hc, Wc), dtype=bool)
flame_box = (body_x0, body_y0, body_x1, body_y1)
sub_lum = Lc_lum[body_y0:body_y1, body_x0:body_x1]
flame_local_mask[body_y0:body_y1, body_x0:body_x1] = sub_lum > 95

N_LANTERN = 28
DUR_LANTERN = 100
MAX_SWING = 5.0  # px, at the bottom of the lantern

lantern_frames = []
for k in range(N_LANTERN):
    t = k / N_LANTERN
    damping = math.exp(-2.6 * t)
    swing = math.sin(2 * math.pi * 2.1 * t) * damping * MAX_SWING
    flicker = 1.0 + 0.18 * math.sin(0.9 * k) + 0.09 * math.sin(2.3 * k + 1.0)

    out_rgb = bg_fill.copy()
    out_alpha = np.zeros((Hc, Wc), dtype=np.float32)

    for y in range(Hc):
        row_mask = mask[y]
        if not row_mask.any():
            continue
        frac = max(0.0, (y - pivot_row) / max(1, (bottom_row - pivot_row)))
        shift = int(round(swing * frac))
        xs = np.where(row_mask)[0]
        src_colors = Lc[y, xs].copy()
        if flame_local_mask[y, xs].any():
            fm = flame_local_mask[y, xs]
            src_colors[fm] = np.clip(src_colors[fm] * flicker, 0, 255)
        new_xs = np.clip(xs + shift, 0, Wc - 1)
        out_rgb[y, new_xs] = src_colors
        out_alpha[y, new_xs] = 255

    rgba = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
    lantern_frames.append(Image.fromarray(rgba, 'RGBA'))

save_transparent_gif(lantern_frames, f'{OUTDIR}/fx-lantern.gif', [DUR_LANTERN] * N_LANTERN)
print('lantern done', Wc, Hc, 'bbox', (lx0, ly0, lx1, ly1))


# ================= TARP: gust ripple through hanging cloth =================
tx0, ty0, tx1, ty1 = 350, 725, 465, 905
Tc = arr0[ty0:ty1, tx0:tx1].copy()
THc, TWc, _ = Tc.shape
T_lum = L0[ty0:ty1, tx0:tx1]
T_R, T_B = R0[ty0:ty1, tx0:tx1], B0[ty0:ty1, tx0:tx1]

# the tarp is a warm brown cloth against a cooler dark-blue/stone background;
# it's also simply brighter than the wall gaps around it in this dim corner.
tarp_mask = (T_lum > 9) & (T_R > T_B)

# clean up: keep only reasonably sized connected structure (skip tiny noise specks)
from scipy.ndimage import label as cc_label
labeled, n = cc_label(tarp_mask)
if n > 0:
    sizes = np.bincount(labeled.ravel()); sizes[0] = 0
    tarp_mask = labeled == sizes.argmax()

# close small internal gaps (fold-shadow pixels that fell under threshold) so the
# whole cloth moves as one coherent piece rather than a scatter of streaks
from scipy.ndimage import binary_closing, binary_dilation
tarp_mask = binary_closing(tarp_mask, structure=np.ones((5, 5)))
tarp_mask = binary_dilation(tarp_mask, iterations=1)

idxT = distance_transform_edt(tarp_mask, return_distances=False, return_indices=True)
bg_fillT = Tc[idxT[0], idxT[1]]

# anchor the ripple near the top attachment point; rows further down sway more
top_anchor_row = 0
bottom_row_t = THc - 1

N_TARP = 22
DUR_TARP = 95
MAX_SWAY = 9.0

tarp_frames = []
for k in range(N_TARP):
    t = k / (N_TARP - 1)
    envelope = math.sin(math.pi * t) ** 0.6  # single gust: rises then settles back to zero

    out_rgb = bg_fillT.copy()
    out_alpha = np.zeros((THc, TWc), dtype=np.float32)

    for y in range(THc):
        row_mask = tarp_mask[y]
        if not row_mask.any():
            continue
        frac = (y - top_anchor_row) / max(1, (bottom_row_t - top_anchor_row))
        wave = math.sin(frac * 7.0 - t * 10.0)
        shift = int(round(MAX_SWAY * frac * envelope * wave))
        xs = np.where(row_mask)[0]
        src_colors = Tc[y, xs]
        new_xs = np.clip(xs + shift, 0, TWc - 1)
        out_rgb[y, new_xs] = src_colors
        out_alpha[y, new_xs] = 255

    rgba = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
    tarp_frames.append(Image.fromarray(rgba, 'RGBA'))

save_transparent_gif(tarp_frames, f'{OUTDIR}/fx-tarp.gif', [DUR_TARP] * N_TARP)
print('tarp done', TWc, THc, 'bbox', (tx0, ty0, tx1, ty1), 'mask px', tarp_mask.sum())

W_img, H_img = img.size
for name, (x0, y0, x1, y1) in [('lantern', (lx0, ly0, lx1, ly1)), ('tarp', (tx0, ty0, tx1, ty1))]:
    print(name, dict(left=round(x0/W_img*100,3), top=round(y0/H_img*100,3),
                      width=round((x1-x0)/W_img*100,3), height=round((y1-y0)/H_img*100,3)))
