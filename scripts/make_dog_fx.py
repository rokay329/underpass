import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, label as cc_label, binary_dilation
import math, os

SCENE = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.png')
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'assets')

img = Image.open(SCENE).convert('RGB')
arr0 = np.array(img).astype(np.float32)

dx0, dy0, dx1, dy1 = 114, 925, 267, 1090
Dc = arr0[dy0:dy1, dx0:dx1].copy()
Hc, Wc, _ = Dc.shape
L0c = 0.299 * Dc[..., 0] + 0.587 * Dc[..., 1] + 0.114 * Dc[..., 2]


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


def fur_mask_in_box(box, thresh=16):
    """Real fur silhouette (not a bounding rectangle) within box, via luminance
    thresholding against the darker background, restricted to the box and to the
    dog's own body (largest connected blob) so stray background specks don't leak in."""
    x0, y0, x1, y1 = box
    m = np.zeros((Hc, Wc), dtype=bool)
    sub = L0c[y0:y1, x0:x1] > thresh
    labeled, n = cc_label(sub)
    if n > 0:
        sizes = np.bincount(labeled.ravel()); sizes[0] = 0
        sub = labeled == sizes.argmax()
    m[y0:y1, x0:x1] = sub
    return m


def build_shift_union(true_mask, shifts, axis_row=True):
    """OR of true_mask shifted (vertically) by every value in shifts."""
    union = np.zeros_like(true_mask)
    ys, xs = np.where(true_mask)
    for s in set(shifts):
        new_ys = ys + s
        valid = (new_ys >= 0) & (new_ys < Hc)
        union[new_ys[valid], xs[valid]] = True
    return union


def make_vertical_shift_gif(box, shifts, out_name, thresh=16, extra_paint=None):
    """extra_paint(canvas_arr, k, shift) -> canvas_arr, optional per-frame extra
    drawing (used for the bark's mouth-darken + sound-burst), applied only to
    already-opaque (real fur) pixels so it can never bleed onto the background."""
    true_mask = fur_mask_in_box(box, thresh)
    union = build_shift_union(true_mask, shifts)
    union_padded = binary_dilation(union, iterations=1)  # swallow the 1px anti-alias rim too

    idx = distance_transform_edt(union_padded, return_distances=False, return_indices=True)
    bg_fill = Dc[idx[0], idx[1]]

    ys, xs = np.where(true_mask)

    frames = []
    for k, shift in enumerate(shifts):
        out_rgb = bg_fill.copy()
        out_alpha = np.where(union_padded, 255, 0).astype(np.uint8)

        new_ys = ys + shift
        valid = (new_ys >= 0) & (new_ys < Hc)
        out_rgb[new_ys[valid], xs[valid]] = Dc[ys[valid], xs[valid]]

        arr = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
        if extra_paint is not None:
            arr = extra_paint(arr, k, shift)
        frames.append(Image.fromarray(arr, 'RGBA'))

    return frames, true_mask, union_padded


# ================= EAR PERK =================
ear_box = (56, 3, 120, 44)
EAR_SHIFTS = [0, -2, -3, -3, -2, 0, -1, 0]
DUR_EAR = 130

ear_frames, _, _ = make_vertical_shift_gif(ear_box, EAR_SHIFTS, 'fx-dog-ear.gif')
save_transparent_gif(ear_frames, f'{OUTDIR}/fx-dog-ear.gif', [DUR_EAR] * len(EAR_SHIFTS))
print('ear perk done, frames', len(EAR_SHIFTS))


# ================= BARK (head bob + mouth open + sound-burst marks) =================
head_box = (48, 2, 122, 92)
mouth_box = (68, 60, 102, 85)
BOB    = [0, 2, 3, 2, 0, 0, 2, 3, 2, 0, 0]
MOUTH  = [0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0]
BURST  = [0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0]
DUR_BARK = 110

nose_sample = Dc[mouth_box[1]:mouth_box[1] + 6, mouth_box[0] + 8:mouth_box[0] + 20]
open_mouth_color = nose_sample.reshape(-1, 3).mean(axis=0) * 0.6

rng = np.random.default_rng(4)
burst_color = (235, 225, 205)
mouth_cx = (mouth_box[0] + mouth_box[2]) / 2
mouth_cy = (mouth_box[1] + mouth_box[3]) / 2

def draw_burst(draw, cx, cy, strength):
    n_dashes = 5
    for i in range(n_dashes):
        ang = (i / n_dashes) * 2 * math.pi + rng.uniform(-0.15, 0.15)
        r0 = 7 + rng.uniform(-1, 1)
        r1 = r0 + 5 + strength * 3
        x0, y0 = cx + math.cos(ang) * r0, cy + math.sin(ang) * r0 * 0.6
        x1, y1 = cx + math.cos(ang) * r1, cy + math.sin(ang) * r1 * 0.6
        draw.line([(x0, y0), (x1, y1)], fill=burst_color, width=1)

def bark_extra(arr, k, bob):
    if MOUTH[k]:
        # only recolor pixels that are ALREADY opaque real fur/mouth content —
        # never force background pixels opaque, so no rectangular dim patch
        my0, my1 = mouth_box[1] + bob, mouth_box[3] + bob
        mx0, mx1 = mouth_box[0], mouth_box[2]
        region_alpha = arr[my0:my1, mx0:mx1, 3]
        opaque = region_alpha > 0
        sub = arr[my0:my1, mx0:mx1, :3].astype(np.float32)
        blended = sub * 0.35 + open_mouth_color[None, None, :] * 0.65
        new_sub = arr[my0:my1, mx0:mx1, :3].copy()
        new_sub[opaque] = np.clip(blended[opaque], 0, 255).astype(np.uint8)
        arr[my0:my1, mx0:mx1, :3] = new_sub

    if BURST[k]:
        canvas = Image.fromarray(arr, 'RGBA')
        draw = ImageDraw.Draw(canvas)
        draw_burst(draw, mouth_cx, mouth_cy + bob, BURST[k])
        arr = np.array(canvas)
    return arr

bark_frames, _, _ = make_vertical_shift_gif(head_box, BOB, 'fx-dog-bark.gif', extra_paint=bark_extra)
save_transparent_gif(bark_frames, f'{OUTDIR}/fx-dog-bark.gif', [DUR_BARK] * len(BOB))
print('bark done, frames', len(BOB))

W_img, H_img = img.size
print('dog bbox %:', dict(
    left=round(dx0/W_img*100,3), top=round(dy0/H_img*100,3),
    width=round((dx1-dx0)/W_img*100,3), height=round((dy1-dy0)/H_img*100,3)
))
