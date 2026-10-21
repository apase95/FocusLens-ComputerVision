import io
import warnings
from urllib.request import urlopen
from urllib.parse import urlsplit
from PIL import Image
from .contracts import Frame


def validate(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ('JPEG', 'PNG') or image.width * image.height > 20_000_000:
                    raise ValueError('Unsupported image or excessive dimensions')
                image.load()
                return Frame(data, image.width, image.height, image.format)
    except (OSError, SyntaxError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError('Invalid image') from exc


def capture(url, *, timeout=5, max_bytes=8_000_000):
    """Fetch one image. Timeout bounds socket operations, not total wall time."""
    if timeout <= 0 or max_bytes <= 0 or urlsplit(url).scheme not in ('http', 'https'):
        raise ValueError('HTTP(S) URL and positive limits required')
    try:
        with urlopen(url, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError('Image exceeds byte limit')
        return validate(data)
    except (OSError, TimeoutError) as exc:
        raise ValueError('Camera HTTP request failed') from exc
