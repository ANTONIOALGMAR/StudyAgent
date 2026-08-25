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
    return {"title": titulo, "app": app} if titulo else None


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


__all__ = ["active_window"]
