import numpy as np
from PIL import Image, ImageDraw
import math, os
from scipy.ndimage import distance_transform_edt, label as cc_label, binary_closing, binary_dilation

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


# ================= LANTERN: body stays put (no swing — was disturbing the wall
# behind it); flame goes out, gutters, then relights, in hard-cut dot steps =================
lx0, ly0, lx1, ly1 = 545, 680, 650, 815
Lc = arr0[ly0:ly1, lx0:lx1].copy()
Hc, Wc, _ = Lc.shape
Lc_lum = L0[ly0:ly1, lx0:lx1]

body_x0, body_x1 = 570 - lx0, 620 - lx0
body_y0, body_y1 = 745 - ly0, 803 - ly0
flame_mask = np.zeros((Hc, Wc), dtype=bool)
sub_lum = Lc_lum[body_y0:body_y1, body_x0:body_x1]
flame_mask[body_y0:body_y1, body_x0:body_x1] = sub_lum > 95

# discrete brightness steps (hard cuts, no smooth interpolation): dims out,
# gutters weakly a couple of times near-dark, then relights past full and settles.
FLICKER = [1.00, 0.68, 0.38, 0.16, 0.06, 0.03, 0.11, 0.04, 0.22,
           0.09, 0.34, 0.62, 0.88, 1.08, 1.00]
N_LANTERN = len(FLICKER)
DUR_LANTERN = 150

lantern_frames = []
for k in range(N_LANTERN):
    out_rgb = Lc.copy()
    out_rgb[flame_mask] = np.clip(out_rgb[flame_mask] * FLICKER[k], 0, 255)
    out_alpha = np.where(flame_mask, 255, 0).astype(np.uint8)
    # only the flame pixels are part of this fx layer; body/wall stay the untouched base
    rgba = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
    lantern_frames.append(Image.fromarray(rgba, 'RGBA'))

save_transparent_gif(lantern_frames, f'{OUTDIR}/fx-lantern.gif', [DUR_LANTERN] * N_LANTERN)
print('lantern done', Wc, Hc, 'frames', N_LANTERN, 'bbox', (lx0, ly0, lx1, ly1))


# ================= TARP: discrete banded gust poses (hard cuts) =================
tx0, ty0, tx1, ty1 = 350, 725, 465, 905
Tc = arr0[ty0:ty1, tx0:tx1].copy()
THc, TWc, _ = Tc.shape
T_lum = L0[ty0:ty1, tx0:tx1]
T_R, T_B = R0[ty0:ty1, tx0:tx1], B0[ty0:ty1, tx0:tx1]

tarp_mask = (T_lum > 9) & (T_R > T_B)
labeled, n = cc_label(tarp_mask)
if n > 0:
    sizes = np.bincount(labeled.ravel()); sizes[0] = 0
    tarp_mask = labeled == sizes.argmax()
tarp_mask = binary_closing(tarp_mask, structure=np.ones((5, 5)))
tarp_mask = binary_dilation(tarp_mask, iterations=1)

idxT = distance_transform_edt(tarp_mask, return_distances=False, return_indices=True)
bg_fillT = Tc[idxT[0], idxT[1]]

rows_with_mask = np.where(tarp_mask.any(axis=1))[0]
top_row, bottom_row = rows_with_mask.min(), rows_with_mask.max()
span = max(1, bottom_row - top_row)

# 4 bands, top (anchored) -> bottom (free edge); each band is a short, hand-stepped
# discrete sequence (no smooth wave formula) so it reads as a few flapping poses.
N_TARP = 10
DUR_TARP = 240
band_seqs = [
    [0,  1, -1,  1,  0, -1,  1,  0, -1, 0],   # band 0 (top, near the tie point) — barely moves
    [0,  3, -2,  3, -2,  2, -1,  1,  0, 0],   # band 1
    [0, -4,  5, -4,  4, -3,  2, -1,  1, 0],   # band 2
    [0,  7, -8,  6, -6,  4, -3,  2, -1, 0],   # band 3 (bottom, free edge) — biggest swing
]
n_bands = len(band_seqs)

band_of_row = np.zeros(THc, dtype=int)
for y in range(THc):
    frac = (y - top_row) / span
    band_of_row[y] = min(int(frac * n_bands), n_bands - 1)

tarp_frames = []
for k in range(N_TARP):
    out_rgb = bg_fillT.copy()
    out_alpha = np.zeros((THc, TWc), dtype=np.float32)

    for y in range(THc):
        row_mask = tarp_mask[y]
        if not row_mask.any():
            continue
        shift = band_seqs[band_of_row[y]][k]
        xs = np.where(row_mask)[0]
        src_colors = Tc[y, xs]
        new_xs = np.clip(xs + shift, 0, TWc - 1)
        out_rgb[y, new_xs] = src_colors
        out_alpha[y, new_xs] = 255

    rgba = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
    tarp_frames.append(Image.fromarray(rgba, 'RGBA'))

save_transparent_gif(tarp_frames, f'{OUTDIR}/fx-tarp.gif', [DUR_TARP] * N_TARP)
print('tarp done', TWc, THc, 'frames', N_TARP, 'bbox', (tx0, ty0, tx1, ty1))

W_img, H_img = img.size
for name, (x0, y0, x1, y1) in [('lantern', (lx0, ly0, lx1, ly1)), ('tarp', (tx0, ty0, tx1, ty1))]:
    print(name, dict(left=round(x0/W_img*100,3), top=round(y0/H_img*100,3),
                      width=round((x1-x0)/W_img*100,3), height=round((y1-y0)/H_img*100,3)))
