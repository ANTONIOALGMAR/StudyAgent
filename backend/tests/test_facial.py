"""Testes do reconhecimento facial por embedding (matcher + persistência)."""

from pathlib import Path

import numpy as np

from app.vision.facial import FaceRecognition


def _mk(name: str, seed: int) -> np.ndarray:
    """Embedding determinístico e L2-normalizado para fins de teste."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512).astype(np.float32)
    return v / np.linalg.norm(v)


def _embedder(map_: dict[str, np.ndarray] | None = None):
    """embed injetado: devolve vetor fixo por bytes (ou None se marcado 'noface')."""
    map_ = map_ or {}
    def embed(image_bytes: bytes) -> np.ndarray | None:
        key = image_bytes.decode("utf-8", "ignore")
        if key == "noface":
            return None
        return map_.get(key)
    return embed


def _recognizer(responses: dict[str, np.ndarray], path: Path | None = None):
    if path is None:
        path = Path(__import__("tempfile").mkdtemp()) / "faces.json"
    return FaceRecognition(path=path, embed=_embedder(responses))


def test_register_and_list(tmp_path):
    ana_v = _mk("ana", 1)
    faces_path = tmp_path / "faces.json"
    fr = _recognizer({"a": ana_v}, path=faces_path)
    fr.register("ana", b"a")
    assert fr.list_faces()[0]["name"] == "ana"
    fr2 = _recognizer({"a": ana_v}, path=faces_path)
    assert fr2.list_faces()[0]["name"] == "ana"


def test_register_rejects_name_missing(tmp_path):
    fr = _recognizer({}, path=tmp_path / "faces.json")
    try:
        fr.register("  ", b"img")
        raise AssertionError("deveria levantar ValueError")
    except ValueError:
        pass


def test_register_rejects_no_face(tmp_path):
    fr = _recognizer({}, path=tmp_path / "faces.json")
    try:
        fr.register("ana", b"noface")
        raise AssertionError("deveria levantar ValueError")
    except ValueError:
        pass


def test_recognize_matches_known_user():
    ana_v = _mk("ana", 1)
    # probe = ana + pequeno ruído -> alta similaridade
    probe = ana_v + np.random.default_rng(7).standard_normal(512).astype(np.float32) * 0.02
    probe = probe / np.linalg.norm(probe)
    fr = _recognizer({"reg": ana_v, "probe": probe})
    fr.register("ana", b"reg")
    out = fr.recognize(b"probe", threshold=0.5)
    assert out["present"] is True
    assert out["name"] == "ana"
    assert out["confidence"] > 0.5


def test_recognize_unknown_when_below_threshold():
    ana_v = _mk("ana", 1)
    outro_v = _mk("outro", 99)
    fr = _recognizer({"reg": ana_v, "probe": outro_v})
    fr.register("ana", b"reg")
    out = fr.recognize(b"probe", threshold=0.8)
    assert out["name"] is None
    assert out["present"] is True


def test_recognize_no_face():
    fr = _recognizer({})
    out = fr.recognize(b"noface")
    assert out["present"] is False
    assert out["name"] is None
