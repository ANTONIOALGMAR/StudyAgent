"""Testes para o pipeline de visão: ScreenManager, engine.process_capture, e objetos."""

from PIL import Image

from app.vision.engine import process_capture
from app.vision.screen import ScreenManager


def test_screen_manager_list_monitors():
    monitors = ScreenManager.list_monitors()
    assert isinstance(monitors, list)
    assert len(monitors) > 0
    assert "index" in monitors[0]
    assert "width" in monitors[0]


def test_screen_manager_validate_monitor():
    assert ScreenManager.validate_monitor(0) is True
    assert ScreenManager.validate_monitor(99) is False


def test_process_capture_builds_context():
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    window_info = {"app": "Pytest", "title": "Unit Test"}

    ctx = process_capture(img, monitor_id=1, window_info=window_info)

    assert ctx.source == "screen"
    assert ctx.monitor_id == 1
    assert ctx.resolution == (100, 100)
    assert ctx.window_app == "Pytest"
    assert ctx.window_title == "Unit Test"
    assert ctx.is_valid is True
    assert "CAPTURED" in ctx.pipeline_stages


def test_process_capture_ocr_useful():
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    ctx = process_capture(img, monitor_id=0)
    # OCR on a blank image returns empty text
    assert ctx.has_ocr is False


def test_process_capture_no_window():
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    ctx = process_capture(img, monitor_id=1, window_info=None)
    assert ctx.window_app is None
    assert ctx.window_title is None
    assert ctx.is_valid is True
