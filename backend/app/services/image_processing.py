"""Pure, synchronous photo clean-up with Pillow. Call it through ``asyncio.to_thread``.

The file the browser uploaded is never trusted: the real format comes from decoding it, the
picture is rotated upright and then re-encoded from its pixels alone, so EXIF (GPS, device,
timestamps), ICC profiles, comments and anything appended to the file are not carried over.
"""

import io
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

# The browser shrinks photos to 1600 px before upload, so anything near this is suspicious. Decoding
# plus the working copies below cost roughly 4 x 3 bytes per pixel (about 200 MB at this cap).
Image.MAX_IMAGE_PIXELS = 16_000_000

THUMB_MAX_SIDE = 1024
SANITISED_JPEG_QUALITY = 85
THUMB_JPEG_QUALITY = 80

# Pillow format name -> (mime type, file extension)
SUPPORTED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


class ImageRejected(Exception):
    """The bytes are not a usable photo. ``reason`` is for logs and the audit trail, not for users."""

    def __init__(self, reason: Literal["not_an_image", "unsupported", "too_large"]):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes  # sanitised original, no metadata
    mime_type: str
    extension: str
    width: int
    height: int
    thumbnail: bytes  # JPEG, longest side <= THUMB_MAX_SIDE


def _flatten_for_jpeg(image: Image.Image) -> Image.Image:
    """RGB copy of ``image``; transparency is flattened onto white."""
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA", "P", "PA") and (image.mode != "P" or "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _encode(image: Image.Image, fmt: str) -> bytes:
    out = io.BytesIO()
    if fmt == "JPEG":
        _flatten_for_jpeg(image).save(out, "JPEG", quality=SANITISED_JPEG_QUALITY, optimize=True)
    elif fmt == "PNG":
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.save(out, "PNG", optimize=True)
    else:
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() or image.mode == "P" else "RGB")
        image.save(out, "WEBP", quality=SANITISED_JPEG_QUALITY)
    return out.getvalue()


def sanitise_image(data: bytes) -> ProcessedImage:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            fmt = opened.format
            if fmt not in SUPPORTED_FORMATS:
                raise ImageRejected("unsupported")
            if opened.width * opened.height > Image.MAX_IMAGE_PIXELS:  # Pillow itself only warns up to twice this
                raise ImageRejected("too_large")
            if getattr(opened, "n_frames", 1) > 1:
                opened.seek(0)  # animated GIF/WEBP/PNG: keep the first frame only
            opened.load()
            upright = ImageOps.exif_transpose(opened)  # returns a copy without the orientation tag
    except ImageRejected:
        raise
    except Image.DecompressionBombError:
        raise ImageRejected("too_large") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        raise ImageRejected("not_an_image") from None

    # Fresh images from the pixels only: nothing in ``info`` (EXIF, ICC, comments) is passed on.
    pixels = Image.frombytes(upright.mode, upright.size, upright.tobytes())
    if upright.mode == "P" and upright.getpalette():
        pixels.putpalette(upright.getpalette())
        if "transparency" in upright.info:
            pixels.info["transparency"] = upright.info["transparency"]

    mime_type, extension = SUPPORTED_FORMATS[fmt]
    sanitised = _encode(pixels, fmt)

    thumb = pixels.copy()
    thumb.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE), Image.Resampling.LANCZOS)
    thumb_out = io.BytesIO()
    _flatten_for_jpeg(thumb).save(thumb_out, "JPEG", quality=THUMB_JPEG_QUALITY, optimize=True)

    return ProcessedImage(
        data=sanitised, mime_type=mime_type, extension=extension,
        width=pixels.width, height=pixels.height, thumbnail=thumb_out.getvalue(),
    )
