import os
import subprocess
import tempfile
import time
from pathlib import Path

import mss
from PIL import Image


def _is_wayland():
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def _looks_black(image: Image.Image) -> bool:
    gray = image.convert("L").resize((64, 36))
    return max(gray.getdata()) <= 8


def _capture_cosmic() -> Image.Image | None:
    out_dir = Path(tempfile.gettempdir()) / "studyagent_shots"
    out_dir.mkdir(exist_ok=True)
    before = set(out_dir.glob("*.png"))
    try:
        subprocess.run(
            [
                "cosmic-screenshot",
                "--interactive=false",
                "--modal=false",
                "--notify=false",
                "-s",
                str(out_dir),
            ],
            check=True,
            timeout=20,
        )
    except Exception:
        return None
    time.sleep(0.3)
    new_files = [p for p in out_dir.glob("*.png") if p not in before]
    if not new_files:
        return None
    latest = max(new_files, key=lambda p: p.stat().st_mtime)
    try:
        return Image.open(latest).convert("RGB")
    finally:
        latest.unlink(missing_ok=True)


def validate_capture(image, monitor: int):
    """Valida imagem capturada e retorna ScreenCaptureResult."""
    from ..core.vision_router import ScreenCaptureResult

    if image is None:
        return ScreenCaptureResult.failed(monitor, "Captura retornou None")
    try:
        result = ScreenCaptureResult.from_image(image, monitor)
        if _looks_black(image):
            result.errors = ["Imagem capturada está preta (provavelmente falha de captura Wayland)"]
            result.is_valid = False
        return result
    except Exception as exc:
        return ScreenCaptureResult.failed(monitor, f"Erro na validação: {exc}")


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


def _crop_virtual(full: Image.Image, monitor: int, region=None) -> Image.Image:
    monitors = list_monitors()
    index = min(max(int(monitor), 0), len(monitors) - 1)
    m = monitors[index]
    virtual_w, virtual_h = monitors[0]["width"], monitors[0]["height"]
    sx = full.width / max(virtual_w, 1)
    sy = full.height / max(virtual_h, 1)
    if region:
        left = float(region.get("left", 0))
        top = float(region.get("top", 0))
        width = float(region.get("width", 800))
        height = float(region.get("height", 600))
    else:
        left, top = float(m["left"]), float(m["top"])
        width, height = float(m["width"]), float(m["height"])
    box = (
        round(left * sx),
        round(top * sy),
        round((left + width) * sx),
        round((top + height) * sy),
    )
    box = (
        max(0, min(box[0], full.width - 1)),
        max(0, min(box[1], full.height - 1)),
        max(box[0] + 1, min(box[2], full.width)),
        max(box[1] + 1, min(box[3], full.height)),
    )
    return full.crop(box)


def capture(monitor=1, region=None) -> Image.Image:
    if _is_wayland():
        full = _capture_cosmic()
        if full is not None and not _looks_black(full):
            return _crop_virtual(full, monitor, region)
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
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if _looks_black(img) and _is_wayland():
        full = _capture_cosmic()
        if full is not None and not _looks_black(full):
            return _crop_virtual(full, monitor, region)
    return img


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
