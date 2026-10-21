"""Bounded decoding and optional, non-mutating mild preprocessing."""
import io
from PIL import Image, ImageOps, ImageFilter
from .camera import validate


def prepare(data, *, enhance=False):
    if len(data) > 8_000_000:
        raise ValueError('Image exceeds 8 MB byte limit')
    validate(data)
    with Image.open(io.BytesIO(data)) as source:
        image = source.convert('RGB')
    changes = []
    if enhance:
        if max(image.size) > 2000:
            image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
            changes.append('max_side=2000')
        image = ImageOps.autocontrast(image, cutoff=0)
        image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=3))
        changes.extend(['autocontrast:cutoff=0', 'unsharp:radius=1,percent=50,threshold=3'])
    return image, changes


def read_image(path):
    with open(path, 'rb') as source:
        data = source.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError('Image exceeds 8 MB byte limit')
    return data
