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
