import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
import math, os

SCENE = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.png')
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'assets')

img = Image.open(SCENE).convert('RGB')
arr0 = np.array(img).astype(np.float32)

dx0, dy0, dx1, dy1 = 114, 925, 267, 1090
Dc = arr0[dy0:dy1, dx0:dx1].copy()
Hc, Wc, _ = Dc.shape


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


def make_rigid_vshift_gif(box, shifts):
    """Rigid vertical shift of the WHOLE box rectangle (eyes, nose, every dark
    detail included -- nothing gets brightness-filtered out, so nothing can be
    mistaken for 'background' and overwritten). Returns per-frame RGBA frames
    plus box_rgb/erased_fill for reuse (e.g. bark's mouth/burst overlay)."""
    x0, y0, x1, y1 = box
    box_rgb = Dc[y0:y1, x0:x1].copy()
    bw, bh = x1 - x0, y1 - y0

    # inpaint the box's own footprint from its surrounding pixels, so erasing
    # it (before repainting the shifted copy) leaves a plausible background
    hole = np.zeros((Hc, Wc), dtype=bool)
    hole[y0:y1, x0:x1] = True
    idx = distance_transform_edt(hole, return_distances=False, return_indices=True)
    erased_fill = Dc[idx[0], idx[1]]

    frames = []
    for shift in shifts:
        canvas = Dc.copy()
        canvas[y0:y1, x0:x1] = erased_fill[y0:y1, x0:x1]

        new_y0, new_y1 = y0 + shift, y1 + shift
        clip_top = max(0, -new_y0)
        clip_bot = max(0, new_y1 - Hc)
        src_y0, src_y1 = clip_top, bh - clip_bot
        dst_y0, dst_y1 = max(0, new_y0), min(Hc, new_y1)
        if dst_y1 > dst_y0:
            canvas[dst_y0:dst_y1, x0:x1] = box_rgb[src_y0:src_y1]

        alpha = np.zeros((Hc, Wc), dtype=np.uint8)
        alpha[y0:y1, x0:x1] = 255          # original footprint (being erased/repainted)
        if dst_y1 > dst_y0:
            alpha[dst_y0:dst_y1, x0:x1] = 255  # shifted footprint (new content)

        frames.append(np.dstack([canvas, alpha]).astype(np.uint8))

    return frames, box_rgb, erased_fill


# ================= EAR PERK (+ three floating hearts, zzz-style) =================
ear_box = (56, 3, 120, 44)
EAR_SHIFTS = [0, -2, -3, -3, -2, 0, -1, 0] + [0] * 16  # perk quickly, then hold while hearts rise
DUR_EAR = 110

ear_arrays, _, _ = make_rigid_vshift_gif(ear_box, EAR_SHIFTS)

def draw_pixel_heart(scale, color):
    """Small blocky pixel-art heart, same technique as the bed's 'z' glyphs."""
    bitmap = [
        "0110110",
        "1111111",
        "1111111",
        "0111110",
        "0011100",
        "0001000",
    ]
    gw, gh = 7, 6
    glyph = Image.new('RGBA', (gw, gh), (0, 0, 0, 0))
    for yy, row in enumerate(bitmap):
        for xx, ch in enumerate(row):
            if ch == '1':
                glyph.putpixel((xx, yy), color)
    return glyph.resize((gw * scale, gh * scale), Image.NEAREST)

def lerp_color(c1, c2, t):
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3))

HEART_BRIGHT = (255, 120, 150)
HEART_DIM = (150, 55, 80)
# ears sit right at the top of this crop (ear_box top = y3, only ~3px of wall
# above them before the crop's hard edge), and above that is open archway/river
# scenery -- not wall -- so the crop can't just be extended upward. Instead,
# spawn the hearts lower (around ear-height, not above the ear tips) and keep
# the rise short enough that even the tallest one never reaches y=0.
heart_specs = [
    dict(start=1,  life=13, scale=2, dx=-8,  dy=-13, x0=74,  y0=23),
    dict(start=6,  life=13, scale=3, dx=2,   dy=-15, x0=87,  y0=21),
    dict(start=11, life=13, scale=2, dx=9,   dy=-13, x0=100, y0=23),
]

ear_frames = []
for k, arr in enumerate(ear_arrays):
    canvas = Image.fromarray(arr, 'RGBA')
    for spec in heart_specs:
        local_k = k - spec['start']
        if 0 <= local_k < spec['life']:
            t = local_k / (spec['life'] - 1)
            if t > 0.85:  # vanish while still comfortably inside the crop
                continue
            fade_t = min(t / 0.65, 1.0)
            color = lerp_color(HEART_BRIGHT, HEART_DIM, fade_t) + (255,)
            glyph = draw_pixel_heart(spec['scale'], color)
            px = int(round(spec['x0'] + spec['dx'] * t))
            py = int(round(spec['y0'] + spec['dy'] * t))
            canvas.alpha_composite(glyph, (px, py))
    ear_frames.append(canvas)

save_transparent_gif(ear_frames, f'{OUTDIR}/fx-dog-ear.gif', [DUR_EAR] * len(EAR_SHIFTS))
print('ear perk + hearts done, frames', len(EAR_SHIFTS))


# ================= BARK (head bob + mouth open + sound-burst marks) =================
head_box = (48, 2, 122, 92)
mouth_box = (68, 60, 102, 85)
BOB    = [0, 2, 3, 2, 0, 0, 2, 3, 2, 0, 0]
MOUTH  = [0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0]
BURST  = [0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0]
DUR_BARK = 110

bark_arrays, _, _ = make_rigid_vshift_gif(head_box, BOB)

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

bark_frames = []
mb_cx = (mouth_box[0] + mouth_box[2]) / 2
mb_cy = (mouth_box[1] + mouth_box[3]) / 2
mb_rx = (mouth_box[2] - mouth_box[0]) / 2
mb_ry = (mouth_box[3] - mouth_box[1]) / 2
myy, mxx = np.mgrid[mouth_box[1]:mouth_box[3], mouth_box[0]:mouth_box[2]]
mouth_dist = np.sqrt(((mxx - mb_cx) / mb_rx) ** 2 + ((myy - mb_cy) / mb_ry) ** 2)
mouth_weight = np.clip(1.0 - mouth_dist, 0, 1) ** 1.4  # soft falloff, 0 at box edges

for k, arr in enumerate(bark_arrays):
    bob = BOB[k]
    if MOUTH[k]:
        my0, my1 = mouth_box[1] + bob, mouth_box[3] + bob
        mx0, mx1 = mouth_box[0], mouth_box[2]
        sub = arr[my0:my1, mx0:mx1, :3].astype(np.float32)
        w = mouth_weight[..., None] * 0.75  # max blend strength at the mouth's center
        blended = sub * (1 - w) + open_mouth_color[None, None, :] * w
        arr[my0:my1, mx0:mx1, :3] = np.clip(blended, 0, 255).astype(np.uint8)
        # alpha already 255 here from the rigid head shift -- no change needed

    canvas = Image.fromarray(arr, 'RGBA')
    if BURST[k]:
        draw = ImageDraw.Draw(canvas)
        draw_burst(draw, mouth_cx, mouth_cy + bob, BURST[k])
    bark_frames.append(canvas)

save_transparent_gif(bark_frames, f'{OUTDIR}/fx-dog-bark.gif', [DUR_BARK] * len(BOB))
print('bark done, frames', len(BOB))

W_img, H_img = img.size
print('dog bbox %:', dict(
    left=round(dx0/W_img*100,3), top=round(dy0/H_img*100,3),
    width=round((dx1-dx0)/W_img*100,3), height=round((dy1-dy0)/H_img*100,3)
))
