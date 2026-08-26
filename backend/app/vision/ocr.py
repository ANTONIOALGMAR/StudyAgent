import shutil

import pytesseract

LANGS = "por+eng"


def available():
    return shutil.which("tesseract") is not None


def read_text(image) -> str:
    if not available():
        raise RuntimeError(
            "Tesseract não instalado. Rode: sudo apt-get install -y "
            "tesseract-ocr tesseract-ocr-por"
        )
    return pytesseract.image_to_string(image, lang=LANGS).strip()


def read_text_structured(image):
    """Retorna OCRResult estruturado em vez de string crua."""
    from ..core.vision_router import OCRResult

    if not available():
        return OCRResult.failed("Tesseract não instalado")
    try:
        raw = pytesseract.image_to_string(image, lang=LANGS).strip()
        return OCRResult.from_text(raw)
    except Exception as exc:
        return OCRResult.failed(str(exc))
