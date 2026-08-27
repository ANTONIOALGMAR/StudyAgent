import shutil

import numpy as np
import pytesseract

from ..core.cache import image_hash, ocr_cache

LANGS = "por+eng"


def available():
    return shutil.which("tesseract") is not None


def _image_to_bytes(image) -> bytes:
    """Converte imagem (PIL/numpy) para bytes para hashing."""
    if isinstance(image, np.ndarray):
        return image.tobytes()
    if hasattr(image, "tobytes"):
        return image.tobytes()
    return str(image).encode()


def read_text(image) -> str:
    if not available():
        raise RuntimeError(
            "Tesseract não instalado. Rode: sudo apt-get install -y "
            "tesseract-ocr tesseract-ocr-por"
        )
    key = image_hash(_image_to_bytes(image))
    cached = ocr_cache.get(key)
    if cached is not None:
        return cached
    result = pytesseract.image_to_string(image, lang=LANGS).strip()
    ocr_cache.set(key, result)
    return result


def read_text_structured(image):
    """Retorna OCRResult estruturado em vez de string crua."""
    from ..core.vision_router import OCRResult

    if not available():
        return OCRResult.failed("Tesseract não instalado")
    try:
        key = image_hash(_image_to_bytes(image))
        cached = ocr_cache.get(key)
        if cached is not None:
            return OCRResult.from_text(cached)
        raw = pytesseract.image_to_string(image, lang=LANGS).strip()
        ocr_cache.set(key, raw)
        return OCRResult.from_text(raw)
    except Exception as exc:
        return OCRResult.failed(str(exc))
