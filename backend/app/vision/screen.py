import mss
from PIL import Image


def capture(monitor=1, region=None) -> Image.Image:
    with mss.mss() as sct:
        if region:
            area = {
                "left": int(region.get("left", 0)),
                "top": int(region.get("top", 0)),
                "width": int(region.get("width", 800)),
                "height": int(region.get("height", 600)),
            }
        else:
            monitors = sct.monitors
            index = min(max(int(monitor), 0), len(monitors) - 1)
            area = monitors[index]
        shot = sct.grab(area)
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def list_monitors():
    with mss.MSS() as sct:
        result = []
        for i, m in enumerate(sct.monitors):
            result.append(
                {
                    "index": i,
                    "width": m["width"],
                    "height": m["height"],
                    "left": m["left"],
                    "top": m["top"],
                }
            )
    return result


def _scale(image: Image.Image, max_width: int) -> Image.Image:
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, int(image.height * ratio)))
    return image


def image_to_base64(image: Image.Image, max_width=1600, quality=85) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    _scale(image, max_width).save(buffer, format="PNG")
    return buffer.getvalue()


def image_to_jpeg_base64(image: Image.Image, max_width=1100, quality=60) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    _scale(image, max_width).save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()
