# Cheap local photo checks, done BEFORE any AI call: is it an image, big enough, bright and sharp?

import io

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
PHOTO_PROBLEMS = {
    "too_small": "The photo is too small. Please take it closer.",
    "too_dark": "The photo is too dark. Please retake it in better light.",
    "too_blurry": "The photo looks blurry or empty. Please retake it.",
}


class NotAnImageError(Exception):
    pass


def readMediaType(imageBytes: bytes) -> str:
    """The real image type (never trust the file name). Raises NotAnImageError."""
    try:
        image = Image.open(io.BytesIO(imageBytes))
        image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise NotAnImageError from error
    if image.format not in MEDIA_TYPES:
        raise NotAnImageError
    return MEDIA_TYPES[image.format]


def findPhotoProblem(imageBytes: bytes) -> str | None:
    """'too_small' | 'too_dark' | 'too_blurry' | None."""
    image = Image.open(io.BytesIO(imageBytes)).convert("L")
    if min(image.size) < 200:
        return "too_small"
    if ImageStat.Stat(image).mean[0] < 35:
        return "too_dark"
    image.thumbnail((512, 512))
    edges = image.filter(ImageFilter.FIND_EDGES)
    width, height = edges.size
    inner = edges.crop((3, 3, width - 3, height - 3))  # the filter marks the border; ignore it
    return "too_blurry" if ImageStat.Stat(inner).stddev[0] < 3.0 else None
