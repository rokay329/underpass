import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_closing, binary_fill_holes
import os

REF = '/mnt/user-data/uploads/1787610526930_image.png'
SCENE = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.png')

# ---- extract the basket: a hand-traced body silhouette (the woven texture is too
# low-contrast for brightness thresholding alone -- that was the cause of the
# jagged/broken edges in the first version) unioned with a brightness mask for the
# carrots/leaf sprigs poking up above the rim ----
ref = Image.open(REF).convert('RGB')
crop_box = (0, 985, 195, 1100)
crop = ref.crop(crop_box)
arr = np.array(crop).astype(np.float32)
Hc, Wc, _ = arr.shape

basket_poly = [
    (30, 55), (45, 50), (70, 45), (95, 44), (120, 43), (140, 42),
    (160, 48), (175, 58), (183, 72), (183, 88), (175, 98),
    (150, 103), (120, 105), (90, 105), (60, 102), (38, 95), (30, 80), (28, 65),
]
poly_img = Image.new('L', (Wc, Hc), 0)
ImageDraw.Draw(poly_img).polygon(basket_poly, fill=255)
poly_mask = np.array(poly_img) > 0

L = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
top_mask = np.zeros((Hc, Wc), dtype=bool)
top_mask[0:60, 20:160] = True  # carrots + leaf sprigs, above/at the rim
bright_mask = (L > 25) & top_mask

combined = poly_mask | bright_mask
combined = binary_closing(combined, structure=np.ones((3, 3)))
combined = binary_fill_holes(combined)

rgba = np.dstack([arr, (combined * 255).astype(np.uint8)]).astype(np.uint8)
basket_cutout = Image.fromarray(rgba, 'RGBA')

# ---- composite onto the small crate at the far left ----
scene = Image.open(SCENE).convert('RGBA')

SCALE = 0.56  # basket crop is wider now (195px), so scale down more than before
                # so its full width fits left of 쿤이's hotspot bbox (x >= 114)
                # without clipping off the canvas edge on the left either
w, h = basket_cutout.size
nw, nh = int(w * SCALE), int(h * SCALE)
basket_scaled = basket_cutout.resize((nw, nh), Image.LANCZOS)

# anchor point: where the basket's base rests on the crate top (nudged left of the
# crate's visual center so it clears 쿤이's hotspot bbox, same as before)
ground_x, ground_y = 56, 1080
x = ground_x - nw // 2
y = ground_y - nh

scene.alpha_composite(basket_scaled, (x, y))
scene.convert('RGB').save(SCENE)
print('saved', SCENE, 'basket placed at', (x, y), 'size', (nw, nh))
print('basket bbox for hotspot-overlap reference:', (x, y, x + nw, y + nh))
