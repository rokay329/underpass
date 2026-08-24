import numpy as np
from PIL import Image
from scipy.ndimage import label, binary_closing, binary_fill_holes
import os

REF = '/mnt/user-data/uploads/1787551723778_image.png'
BASE_SCENE = '/home/claude/scene_original_backup.png'  # clean scene, no dog composited yet
SCENE = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.png')

# ---- extract a clean dog cutout from the reference image ----
ref = Image.open(REF).convert('RGB')
dog_box = (255, 935, 435, 1130)
dog_rgb = ref.crop(dog_box)
arr = np.array(dog_rgb).astype(np.float32)
L = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]

mask = L > 22
labeled, n = label(mask)
sizes = np.bincount(labeled.ravel()); sizes[0] = 0
mask = labeled == sizes.argmax()
mask = binary_closing(mask, structure=np.ones((4, 4)))
mask = binary_fill_holes(mask)

rgba = np.dstack([arr, (mask * 255).astype(np.uint8)]).astype(np.uint8)
dog_cutout = Image.fromarray(rgba, 'RGBA')

# ---- composite into the scene, on the path between the crates and the firepit ----
scene = Image.open(BASE_SCENE).convert('RGBA')

SCALE = 0.85
w, h = dog_cutout.size
nw, nh = int(w * SCALE), int(h * SCALE)
dog_scaled = dog_cutout.resize((nw, nh), Image.LANCZOS)

# anchor point: where the dog's paws touch the ground
ground_x, ground_y = 190, 1090
x = ground_x - nw // 2
y = ground_y - nh

scene.alpha_composite(dog_scaled, (x, y))
scene.convert('RGB').save(SCENE)
print('saved', SCENE, 'dog placed at', (x, y), 'size', (nw, nh))
print('dog bbox for hotspot-overlap reference:', (x, y, x + nw, y + nh))
