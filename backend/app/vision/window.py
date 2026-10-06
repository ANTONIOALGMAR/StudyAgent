"""Janela ativa: melhor esforço multi-plataforma.

Wayland não expõe janelas sem suporte do compositor; tentamos estratégias
na ordem e devolvemos None com silêncio quando nada está disponível.
"""

import json
import shutil
import subprocess


def active_window() -> dict | None:
    for estrategia in (_via_xdotool, _via_sway):
        try:
            info = estrategia()
        except Exception:
            continue
        if info:
            return info
    return None


def active_window_rect() -> dict | None:
    """Retorna só a geometria da janela ativa (posição e tamanho).

    É o que permite descobrir em qual das telas o comando foi dado.
    """
    info = active_window()
    if not info:
        return None
    return _rect_from_window(info)


def _rect_from_window(info: dict) -> dict | None:
    rect = {
        "left": info.get("left"),
        "top": info.get("top"),
        "width": info.get("width"),
        "height": info.get("height"),
    }
    if any(v is None for v in rect.values()):
        return None
    if rect["width"] <= 0 or rect["height"] <= 0:
        return None
    rect["right"] = rect["left"] + rect["width"]
    rect["bottom"] = rect["top"] + rect["height"]
    return rect


def _via_xdotool():
    if not shutil.which("xdotool"):
        return None
    wid = subprocess.run(
        ["xdotool", "getactivewindow"],
        capture_output=True, text=True, timeout=3,
    ).stdout.strip()
    if not wid.isdigit():
        return None

    def prop(name):
        out = subprocess.run(
            ["xdotool", "getwindowname", wid] if name == "title" else ["xprop", "-id", wid, "WM_CLASS"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        return out

    titulo = prop("title")
    app = ""
    xprop_out = subprocess.run(
        ["xprop", "-id", wid, "WM_CLASS"], capture_output=True, text=True, timeout=3
    ).stdout
    if '"' in xprop_out:
        app = xprop_out.split('"')[1::2][-1] if len(xprop_out.split('"')) > 2 else ""
    if not titulo:
        return None
    janela = {"title": titulo, "app": app}
    janela.update(_x11_geometry(wid))
    return janela


def _x11_geometry(wid: str) -> dict:
    """Geometria da janela via xdotool --shell (X11/COSMIC com XWayland)."""

    if not shutil.which("xdotool"):
        return {}

    try:
        out = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", wid],
            capture_output=True, text=True, timeout=3,
        ).stdout
    except Exception:
        return {}

    valores = {}
    for linha in out.splitlines():
        chave, _, valor = linha.partition("=")
        try:
            valores[chave.strip().lower()] = int(float(valor.strip()))
        except (TypeError, ValueError):
            continue

    esquerda = valores.get("x")
    topo = valores.get("y")
    largura = valores.get("width")
    altura = valores.get("height")

    if None in (esquerda, topo, largura, altura):
        return {}

    return {
        "left": esquerda,
        "top": topo,
        "width": largura,
        "height": altura,
    }


def _via_sway():
    if not shutil.which("swaymsg"):
        return None
    tree = json.loads(
        subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True, text=True, timeout=3,
        ).stdout
    )
    achado = {}

    def walk(node):
        if achado:
            return
        if node.get("focused"):
            achado["title"] = node.get("name", "")
            pid = node.get("pid")
            achado["app"] = _app_do_pid(pid)
            rect = node.get("rect") or {}
            if all(k in rect for k in ("x", "y", "width", "height")):
                achado["left"] = rect.get("x")
                achado["top"] = rect.get("y")
                achado["width"] = rect.get("width")
                achado["height"] = rect.get("height")
            return
        for filho in node.get("nodes", []) + node.get("floating_nodes", []):
            walk(filho)

    walk(tree)
    return achado or None


def _app_do_pid(pid):
    if not pid:
        return ""
    try:
        cmdline = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="ignore")
        return cmdline.split("\0")[0].split("/")[-1]
    except OSError:
        return ""


__all__ = ["active_window", "active_window_rect"]
