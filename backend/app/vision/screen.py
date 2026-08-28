from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import mss
from PIL import Image

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

_CAPTURE_DIR = Path(tempfile.gettempdir()) / "studyagent_shots"

# Tempo máximo para o cosmic-screenshot responder.
_COSMIC_TIMEOUT = 20

# Pequena espera para garantir que o arquivo terminou de ser gravado.
_CAPTURE_SETTLE_TIME = 0.15

# Cache da geometria dos monitores.
_MONITOR_CACHE: Optional[list[dict]] = None

# Cache do backend utilizado.
_BACKEND_CACHE: Optional[str] = None


# ============================================================================
# EXCEÇÕES
# ============================================================================


class ScreenCaptureError(RuntimeError):
    """Erro controlado relacionado à captura de tela."""


# ============================================================================
# DETECÇÃO DO AMBIENTE
# ============================================================================


def _is_wayland() -> bool:
    """Retorna True quando a sessão gráfica atual é Wayland."""

    session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()

    if session_type == "wayland":
        return True

    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _is_x11() -> bool:
    """Retorna True quando existe uma sessão X11 utilizável."""

    display = os.environ.get("DISPLAY", "").strip()

    if not display:
        return False

    session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()

    if session_type == "x11":
        return True

    # Em ambientes híbridos, DISPLAY pode existir mesmo em Wayland.
    # Não consideramos isso suficiente para escolher X11.
    return False


def _is_cosmic() -> bool:
    """Detecta o desktop COSMIC."""

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    session_desktop = os.environ.get("XDG_SESSION_DESKTOP", "").lower()

    return "cosmic" in desktop or "cosmic" in session_desktop


def _cosmic_screenshot_available() -> bool:
    """Verifica se cosmic-screenshot está disponível."""

    if not _is_wayland():
        return False

    try:
        result = subprocess.run(
            ["which", "cosmic-screenshot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )

        return result.returncode == 0

    except Exception:
        return False


# ============================================================================
# DESCOBERTA DE MONITORES
# ============================================================================


def _parse_xrandr_monitors() -> list[dict]:
    """
    Descobre monitores usando xrandr.

    O objetivo aqui NÃO é capturar a tela.

    O xrandr é utilizado somente para descobrir:
      - nome
      - largura
      - altura
      - posição X
      - posição Y

    Isso é especialmente importante no Wayland/COSMIC porque o
    mss pode não conseguir acessar corretamente a sessão gráfica.
    """

    try:
        result = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    except FileNotFoundError:
        return []

    except Exception:
        return []

    if result.returncode != 0:
        return []

    monitors: list[dict] = []

    # Exemplo:
    #
    #  0: +HDMI-A-1 1920/480x1080/270+2806+0 HDMI-A-1
    #
    pattern = re.compile(
        r"""
        ^\s*
        (?P<index>\d+):
        \s*
        [+\-]?
        (?P<name>[A-Za-z0-9_.:-]+)
        \s+
        (?P<width>\d+)
        /
        [\d.]+
        x
        (?P<height>\d+)
        /
        [\d.]+
        (?P<left>[+\-]\d+)
        (?P<top>[+\-]\d+)
        """,
        re.VERBOSE,
    )

    for line in result.stdout.splitlines():

        match = pattern.match(line)

        if not match:
            continue

        try:
            index = int(match.group("index"))
            name = match.group("name")
            width = int(match.group("width"))
            height = int(match.group("height"))
            left = int(match.group("left"))
            top = int(match.group("top"))

        except (TypeError, ValueError):
            continue

        monitors.append(
            {
                "index": index,
                "name": name,
                "width": width,
                "height": height,
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
            }
        )

    return monitors


def _parse_xrandr_query() -> list[dict]:
    """
    Fallback de descoberta utilizando xrandr --query.

    Útil quando --listmonitors não estiver disponível.
    """

    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    if result.returncode != 0:
        return []

    monitors: list[dict] = []

    # Exemplo:
    #
    # HDMI-A-1 connected 1920x1080+2806+0
    #
    pattern = re.compile(
        r"""
        ^
        (?P<name>\S+)
        \s+
        connected
        (?:\s+primary)?
        \s+
        (?P<width>\d+)x(?P<height>\d+)
        \+
        (?P<left>\d+)
        \+
        (?P<top>\d+)
        """,
        re.VERBOSE,
    )

    for line in result.stdout.splitlines():

        match = pattern.match(line.strip())

        if not match:
            continue

        try:
            name = match.group("name")
            width = int(match.group("width"))
            height = int(match.group("height"))
            left = int(match.group("left"))
            top = int(match.group("top"))

        except (TypeError, ValueError):
            continue

        monitors.append(
            {
                "index": len(monitors),
                "name": name,
                "width": width,
                "height": height,
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
            }
        )

    return monitors


def _discover_monitors(force_refresh: bool = False) -> list[dict]:
    """
    Descobre e normaliza os monitores.

    A ordem retornada é a ordem apresentada pelo xrandr.

    Para sua máquina:

        0 -> HDMI-A-1
        1 -> DP-1
        2 -> HDMI-A-2

    """

    global _MONITOR_CACHE

    if _MONITOR_CACHE is not None and not force_refresh:
        return [dict(m) for m in _MONITOR_CACHE]

    monitors = _parse_xrandr_monitors()

    if not monitors:
        monitors = _parse_xrandr_query()

    # Se não conseguimos descobrir por xrandr e estamos em X11,
    # tentamos mss apenas para descoberta.
    if not monitors and _is_x11():

        try:
            with mss.MSS() as sct:

                monitors = []

                for index, monitor in enumerate(sct.monitors):

                    monitors.append(
                        {
                            "index": index,
                            "name": f"mss-{index}",
                            "width": int(monitor["width"]),
                            "height": int(monitor["height"]),
                            "left": int(monitor["left"]),
                            "top": int(monitor["top"]),
                            "right": int(monitor["left"])
                            + int(monitor["width"]),
                            "bottom": int(monitor["top"])
                            + int(monitor["height"]),
                        }
                    )

        except Exception:
            monitors = []

    # Normaliza índices.
    normalized: list[dict] = []

    for index, monitor in enumerate(monitors):

        item = dict(monitor)

        item["index"] = index

        item["width"] = int(item["width"])
        item["height"] = int(item["height"])
        item["left"] = int(item["left"])
        item["top"] = int(item["top"])

        item["right"] = item["left"] + item["width"]
        item["bottom"] = item["top"] + item["height"]

        normalized.append(item)

    _MONITOR_CACHE = normalized

    return [dict(m) for m in normalized]


def _virtual_geometry(monitors: list[dict]) -> dict:
    """
    Calcula a geometria real do desktop virtual.

    IMPORTANTE:

    Não podemos utilizar monitors[0]["width"] como largura virtual.

    No seu computador:

        monitor 0 = 1920
        monitor 1 = 1440
        monitor 2 = 1365

    porém o desktop virtual possui:

        4726 × 1080

    calculado a partir das coordenadas dos monitores.
    """

    if not monitors:
        raise ScreenCaptureError("Nenhum monitor foi detectado.")

    left = min(m["left"] for m in monitors)
    top = min(m["top"] for m in monitors)

    right = max(m["right"] for m in monitors)
    bottom = max(m["bottom"] for m in monitors)

    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


# ============================================================================
# SCREEN MANAGER
# ============================================================================


class ScreenManager:
    """Gerenciador profissional de monitores e captura de tela."""

    @staticmethod
    def list_monitors() -> list[dict]:
        """Lista todos os monitores detectados."""

        return _discover_monitors()

    @staticmethod
    def get_monitor(monitor_id: int) -> Optional[dict]:
        """Busca dados de um monitor específico."""

        monitors = _discover_monitors()

        try:
            monitor_id = int(monitor_id)
        except (TypeError, ValueError):
            return None

        if 0 <= monitor_id < len(monitors):
            return dict(monitors[monitor_id])

        return None

    @staticmethod
    def validate_monitor(monitor_id: int) -> bool:
        """Verifica se o ID do monitor é válido."""

        return ScreenManager.get_monitor(monitor_id) is not None

    @staticmethod
    def capture_monitor(
        monitor_id: int,
        region: Optional[dict] = None,
    ) -> Image.Image:
        """Captura o monitor solicitado."""

        return _capture(
            monitor=monitor_id,
            region=region,
        )

    @staticmethod
    def refresh_monitors() -> list[dict]:
        """Força nova descoberta dos monitores."""

        return _discover_monitors(force_refresh=True)

    @staticmethod
    def backend() -> str:
        """Retorna o backend de captura selecionado."""

        return _select_backend()


# ============================================================================
# API LEGADA
# ============================================================================


def list_monitors() -> list[dict]:
    """Wrapper legado — usa ScreenManager."""

    return ScreenManager.list_monitors()


def capture(
    monitor: int = 1,
    region: Optional[dict] = None,
) -> Image.Image:
    """Captura de tela pública usada pelos routers."""

    return _capture(
        monitor=monitor,
        region=region,
    )


def validate_capture(image, monitor: int):
    """Valida imagem capturada e retorna ScreenCaptureResult."""

    from ..core.vision_router import ScreenCaptureResult

    if image is None:
        return ScreenCaptureResult.failed(
            monitor,
            "Captura retornou None",
        )

    try:
        result = ScreenCaptureResult.from_image(
            image,
            monitor,
        )

        if _looks_black(image):

            result.error = (
                "Imagem preta ou praticamente preta. "
                "O backend de captura não retornou conteúdo visual."
            )

            result.is_valid = False

        return result

    except Exception as exc:

        return ScreenCaptureResult.failed(
            monitor,
            f"Erro na validação: {exc}",
        )


# ============================================================================
# CAPTURA COSMIC / WAYLAND
# ============================================================================


def _capture_cosmic() -> Image.Image:
    """
    Captura o desktop virtual completo utilizando cosmic-screenshot.

    O COSMIC retorna uma imagem única do desktop virtual.

    Exemplo da máquina atual:

        4726 × 1080

    Depois essa imagem é recortada utilizando a geometria obtida pelo xrandr.
    """

    if not _cosmic_screenshot_available():

        raise ScreenCaptureError(
            "cosmic-screenshot não está disponível "
            "para a sessão Wayland atual."
        )

    _CAPTURE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Remove somente screenshots antigas do StudyAgent.
    for old_file in _CAPTURE_DIR.glob("*.png"):

        try:
            old_file.unlink()

        except OSError:
            pass

    before = set(_CAPTURE_DIR.glob("*.png"))

    command = [
        "cosmic-screenshot",
        "--interactive=false",
        "--modal=false",
        "--notify=false",
        "--save-dir",
        str(_CAPTURE_DIR),
    ]

    try:

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=_COSMIC_TIMEOUT,
        )

    except subprocess.TimeoutExpired as exc:

        raise ScreenCaptureError(
            "cosmic-screenshot excedeu o tempo máximo "
            f"de {_COSMIC_TIMEOUT}s."
        ) from exc

    except Exception as exc:

        raise ScreenCaptureError(
            f"Falha ao executar cosmic-screenshot: {exc}"
        ) from exc

    if completed.returncode != 0:

        stderr = (completed.stderr or "").strip()

        stdout = (completed.stdout or "").strip()

        details = stderr or stdout or "sem detalhes"

        raise ScreenCaptureError(
            "cosmic-screenshot retornou erro: "
            f"{details}"
        )

    # Pequena espera para finalização do arquivo.
    time.sleep(_CAPTURE_SETTLE_TIME)

    files = [
        p
        for p in _CAPTURE_DIR.glob("*.png")
        if p not in before
    ]

    # Alguns ambientes podem reutilizar o arquivo.
    if not files:

        files = list(_CAPTURE_DIR.glob("*.png"))

    if not files:

        raise ScreenCaptureError(
            "cosmic-screenshot terminou sem produzir "
            "nenhum arquivo PNG."
        )

    latest = max(
        files,
        key=lambda p: p.stat().st_mtime,
    )

    try:

        with Image.open(latest) as source:

            image = source.convert("RGB")

            # copy() garante que a imagem não dependa mais
            # do arquivo aberto.
            image = image.copy()

    except Exception as exc:

        raise ScreenCaptureError(
            f"Não foi possível abrir a captura "
            f"{latest}: {exc}"
        ) from exc

    finally:

        try:
            latest.unlink(missing_ok=True)

        except OSError:
            pass

    if image.width <= 1 or image.height <= 1:

        raise ScreenCaptureError(
            f"Captura inválida: {image.size}"
        )

    return image


# ============================================================================
# CAPTURA X11 / MSS
# ============================================================================


def _capture_mss(
    monitor: int,
    region: Optional[dict] = None,
) -> Image.Image:
    """Captura via MSS exclusivamente em X11."""

    if not _is_x11():

        raise ScreenCaptureError(
            "MSS foi solicitado, mas a sessão atual "
            "não foi identificada como X11."
        )

    try:

        with mss.MSS() as sct:

            monitors = sct.monitors

            if monitor < 0 or monitor >= len(monitors):

                raise ScreenCaptureError(
                    f"Monitor {monitor} inválido. "
                    f"Disponíveis: 0..{len(monitors) - 1}"
                )

            if region:

                area = {
                    "left": int(region.get("left", 0)),
                    "top": int(region.get("top", 0)),
                    "width": int(
                        region.get("width", 800)
                    ),
                    "height": int(
                        region.get("height", 600)
                    ),
                }

            else:

                area = monitors[monitor]

            shot = sct.grab(area)

            image = Image.frombytes(
                "RGB",
                shot.size,
                shot.bgra,
                "raw",
                "BGRX",
            )

            return image.copy()

    except ScreenCaptureError:
        raise

    except Exception as exc:

        raise ScreenCaptureError(
            f"Falha na captura MSS/X11: {exc}"
        ) from exc


# ============================================================================
# BACKEND
# ============================================================================


def _select_backend(force_refresh: bool = False) -> str:
    """
    Seleciona o backend correto.

    Prioridade:

        Wayland + COSMIC
            ↓
        cosmic-screenshot

        X11
            ↓
        MSS

    Nunca usamos MSS como fallback automático de Wayland.
    """

    global _BACKEND_CACHE

    if _BACKEND_CACHE is not None and not force_refresh:
        return _BACKEND_CACHE

    if _is_wayland():

        if _cosmic_screenshot_available():

            _BACKEND_CACHE = "cosmic"

            return _BACKEND_CACHE

        raise ScreenCaptureError(
            "Sessão Wayland detectada, porém "
            "cosmic-screenshot não está disponível."
        )

    if _is_x11():

        _BACKEND_CACHE = "mss"

        return _BACKEND_CACHE

    raise ScreenCaptureError(
        "Não foi possível identificar um backend "
        "de captura compatível. "
        f"XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', '')!r}, "
        f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')!r}, "
        f"DISPLAY={os.environ.get('DISPLAY', '')!r}"
    )


# ============================================================================
# GEOMETRIA / CROP
# ============================================================================


def _crop_virtual(
    full: Image.Image,
    monitor: int,
    region: Optional[dict] = None,
) -> Image.Image:
    """
    Recorta um monitor a partir da captura virtual completa.

    A captura COSMIC está em coordenadas de pixels da imagem.

    A geometria do xrandr também é baseada em pixels.

    Portanto, quando:

        full = 4726 × 1080

    e:

        virtual = 4726 × 1080

    a escala será:

        sx = 1
        sy = 1

    Mesmo assim mantemos o cálculo proporcional para suportar
    diferenças futuras de escala.
    """

    monitors = _discover_monitors()

    if not monitors:

        raise ScreenCaptureError(
            "Nenhum monitor detectado para realizar o crop."
        )

    try:
        monitor = int(monitor)

    except (TypeError, ValueError) as exc:

        raise ScreenCaptureError(
            f"ID de monitor inválido: {monitor!r}"
        ) from exc

    if monitor < 0 or monitor >= len(monitors):

        raise ScreenCaptureError(
            f"Monitor {monitor} inválido. "
            f"Disponíveis: 0..{len(monitors) - 1}"
        )

    virtual = _virtual_geometry(monitors)

    # Coordenadas absolutas do desktop virtual.
    virtual_left = virtual["left"]
    virtual_top = virtual["top"]

    # Escala entre geometria lógica e imagem capturada.
    sx = full.width / max(
        virtual["width"],
        1,
    )

    sy = full.height / max(
        virtual["height"],
        1,
    )

    if region:

        left = float(
            region.get("left", 0)
        )

        top = float(
            region.get("top", 0)
        )

        width = float(
            region.get("width", 800)
        )

        height = float(
            region.get("height", 600)
        )

    else:

        selected = monitors[monitor]

        left = float(selected["left"])
        top = float(selected["top"])
        width = float(selected["width"])
        height = float(selected["height"])

    # Converte coordenadas absolutas do desktop para coordenadas
    # relativas ao desktop virtual.
    relative_left = left - virtual_left
    relative_top = top - virtual_top

    x1 = round(relative_left * sx)
    y1 = round(relative_top * sy)

    x2 = round(
        (relative_left + width) * sx
    )

    y2 = round(
        (relative_top + height) * sy
    )

    # Limita aos limites reais da imagem.
    x1 = max(
        0,
        min(x1, full.width - 1),
    )

    y1 = max(
        0,
        min(y1, full.height - 1),
    )

    x2 = max(
        x1 + 1,
        min(x2, full.width),
    )

    y2 = max(
        y1 + 1,
        min(y2, full.height),
    )

    cropped = full.crop(
        (
            x1,
            y1,
            x2,
            y2,
        )
    )

    if cropped.width <= 1 or cropped.height <= 1:

        raise ScreenCaptureError(
            "Crop resultou em uma imagem inválida: "
            f"{cropped.size}"
        )

    return cropped


# ============================================================================
# CAPTURA PRINCIPAL
# ============================================================================


def _capture(
    monitor=1,
    region: Optional[dict] = None,
) -> Image.Image:
    """
    Captura um monitor.

    Wayland/COSMIC:

        captura desktop inteiro
        ↓
        identifica geometria
        ↓
        recorta monitor solicitado

    X11:

        captura diretamente pelo MSS.
    """

    try:
        monitor = int(monitor)

    except (TypeError, ValueError) as exc:

        raise ScreenCaptureError(
            f"Monitor inválido: {monitor!r}"
        ) from exc

    backend = _select_backend()

    # ------------------------------------------------------------------
    # WAYLAND / COSMIC
    # ------------------------------------------------------------------

    if backend == "cosmic":

        # Descobre antes para validar o monitor.
        monitors = _discover_monitors()

        if not monitors:

            raise ScreenCaptureError(
                "Wayland/COSMIC está disponível, "
                "mas nenhum monitor foi descoberto."
            )

        if monitor < 0 or monitor >= len(monitors):

            raise ScreenCaptureError(
                f"Monitor {monitor} inválido. "
                f"Disponíveis: 0..{len(monitors) - 1}"
            )

        full = _capture_cosmic()

        if _looks_black(full):

            raise ScreenCaptureError(
                "COSMIC retornou uma captura preta. "
                "A captura foi rejeitada para evitar "
                "que o agente tente interpretar uma "
                "imagem inválida."
            )

        return _crop_virtual(
            full,
            monitor,
            region,
        )

    # ------------------------------------------------------------------
    # X11 / MSS
    # ------------------------------------------------------------------

    if backend == "mss":

        image = _capture_mss(
            monitor,
            region,
        )

        if _looks_black(image):

            raise ScreenCaptureError(
                "MSS retornou uma imagem preta."
            )

        return image

    raise ScreenCaptureError(
        f"Backend de captura desconhecido: {backend}"
    )


# ============================================================================
# VALIDAÇÃO DE IMAGEM
# ============================================================================


def _looks_black(image: Image.Image) -> bool:
    """
    Detecta imagens completamente ou praticamente pretas.

    Implementação compatível com Pillow atual sem utilizar
    Image.getdata(), evitando o warning de depreciação.
    """

    if image is None:
        return True

    try:

        gray = image.convert("L").resize(
            (64, 36)
        )

        extrema = gray.getextrema()

        maximum = extrema[1]

        return maximum <= 8

    except Exception:
        return False


# ============================================================================
# ESCALA
# ============================================================================


def _scale(
    image: Image.Image,
    max_width: int,
) -> Image.Image:
    """Reduz uma imagem mantendo a proporção."""

    if max_width <= 0:
        return image

    if image.width <= max_width:
        return image

    ratio = max_width / image.width

    new_size = (
        max_width,
        max(
            1,
            int(image.height * ratio),
        ),
    )

    return image.resize(
        new_size,
        Image.Resampling.LANCZOS,
    )


# ============================================================================
# SERIALIZAÇÃO
# ============================================================================


def image_to_base64(
    image: Image.Image,
    max_width=0,
    quality=90,
) -> bytes:
    """
    Serializa a captura para o modelo de visão.

    max_width:
        0 = preserva a resolução original.
        >0 = reduz proporcionalmente até essa largura.

    quality:
        Qualidade JPEG de 1 a 95.

    IMPORTANTE:
        A captura original nunca é modificada.
        O redimensionamento ocorre somente na cópia
        destinada ao modelo de visão.
    """

    if image is None:
        raise ValueError("Imagem não pode ser None.")

    if image.width <= 0 or image.height <= 0:
        raise ValueError(
            f"Dimensões de imagem inválidas: {image.size}"
        )

    buffer = BytesIO()

    scaled = _scale(
        image,
        max_width,
    )

    scaled.save(
        buffer,
        format="JPEG",
        quality=max(1, min(int(quality), 95)),
        optimize=True,
    )

    return buffer.getvalue()



def image_to_jpeg_base64(
    image: Image.Image,
    max_width=0,
    quality=90,
) -> bytes:
    """Retorna JPEG preservando a resolução original por padrão."""

    if image is None:
        raise ValueError("Imagem não pode ser None.")

    buffer = BytesIO()

    scaled = _scale(
        image,
        max_width,
    )

    scaled.save(
        buffer,
        format="JPEG",
        quality=max(1, min(int(quality), 95)),
        optimize=True,
    )

    return buffer.getvalue()


# ============================================================================
# DIAGNÓSTICO
# ============================================================================


def diagnostics() -> dict:
    """
    Retorna informações úteis para diagnóstico do sistema de visão.

    Não captura a tela.
    """

    monitors = _discover_monitors()

    virtual = None

    if monitors:

        virtual = _virtual_geometry(
            monitors
        )

    backend = None
    backend_error = None

    try:

        backend = _select_backend()

    except Exception as exc:

        backend_error = str(exc)

    return {
        "session_type": os.environ.get(
            "XDG_SESSION_TYPE"
        ),
        "wayland_display": os.environ.get(
            "WAYLAND_DISPLAY"
        ),
        "x11_display": os.environ.get(
            "DISPLAY"
        ),
        "desktop": os.environ.get(
            "XDG_CURRENT_DESKTOP"
        ),
        "session_desktop": os.environ.get(
            "XDG_SESSION_DESKTOP"
        ),
        "is_wayland": _is_wayland(),
        "is_x11": _is_x11(),
        "is_cosmic": _is_cosmic(),
        "cosmic_screenshot_available": (
            _cosmic_screenshot_available()
        ),
        "backend": backend,
        "backend_error": backend_error,
        "monitors": monitors,
        "virtual_geometry": virtual,
    }


# ============================================================================
# RESET DE CACHE
# ============================================================================


def reset_cache() -> None:
    """Limpa caches de backend e geometria."""

    global _MONITOR_CACHE
    global _BACKEND_CACHE

    _MONITOR_CACHE = None
    _BACKEND_CACHE = None
