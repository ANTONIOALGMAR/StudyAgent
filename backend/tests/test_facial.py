"""Testes do reconhecimento facial (matcher + persistência)."""

from pathlib import Path

from app.vision.facial import FaceRecognition, _extract_json, _normalize_features


def _analyze_say(text: str):
    def branch(image_bytes):
        return image_bytes.decode("utf-8", "ignore")
    # ignore image_bytes; return fixed text
    return lambda image_bytes: text


def _recognizer(responses: dict):
    """analyze injetado: devolve texto conforme bytes (que equivalem a chave)."""
    return FaceRecognition(analyze=lambda b: responses.get(b.decode("utf-8"), "{}"))


def test_extract_json_robust():
    assert _extract_json('texto {"present": true, "features": "x"} resto') == {
        "present": True,
        "features": "x",
    }
    assert _extract_json("sem json") == {"present": False, "features": ""}
    assert _extract_json(None) == {"present": False, "features": ""}


def test_normalize_features_canonical():
    toks = _normalize_features("genero: masculino; pele: media; cabelo..cor: PRETO")
    # pontuação e acentos removidos das chaves/valores
    assert "genero:masculino" in toks
    assert "pele:media" in toks
    assert "cabelocor:preto" in toks


def test_register_and_list(tmp_path):
    resp = {
        "a": '{"present": true, "features": "genero: masculino; idade_faixa: adulto; pele: media; cabelo..comprimento: curto; cabelo..cor: preto; occlos: sim; barba: nao"}',
    }
    fr = _recognizer(resp)
    fr._path = tmp_path / "faces.json"
    fr.register("ana", b"a")
    assert fr.list_faces() == [{"name": "ana", "created_at": fr.list_faces()[0]["created_at"]}]
    # persistência
    fr2 = _recognizer(resp)
    fr2._path = tmp_path / "faces.json"
    fr2._load()
    assert fr2.list_faces()[0]["name"] == "ana"


def test_register_rejects_name_missing(tmp_path):
    fr = FaceRecognition(path=tmp_path / "faces.json", analyze=lambda b: '{"present": true, "features": "pele: media"}')
    try:
        fr.register("  ", b"img")
        raise AssertionError("deveria levantar ValueError")
    except ValueError:
        pass


def test_register_rejects_no_face(tmp_path):
    fr = FaceRecognition(path=tmp_path / "faces.json", analyze=lambda b: '{"present": false, "features": ""}')
    try:
        fr.register("ana", b"img")
        raise AssertionError("deveria levantar ValueError")
    except ValueError:
        pass


def test_recognize_matches_known_user():
    ana = ('{"present": true, "features": "genero: masculino; pele: media; cabelo..cor: preto; occlos: sim"}')
    resp = {
        "reg": ana,
        "probe": ('{"present": true, "features": "genero: masculino; pele: media; cabelo..cor: preto; occlos: sim; idade_faixa: adulto"}'),
    }
    fr = _recognizer(resp)
    fr._path = Path(__import__("tempfile").mkdtemp()) / "faces.json"
    fr.register("ana", b"reg")
    out = fr.recognize(b"probe", threshold=0.3)
    assert out["present"] is True
    assert out["name"] == "ana"
    assert out["confidence"] > 0.3


def test_recognize_unknown_when_below_threshold():
    resp = {
        "reg": '{"present": true, "features": "genero: masculino; occlos: sim; pele: media"}',
        "probe": '{"present": true, "features": "genero: feminino; idade_faixa: idoso; cabelo..cor: louro"}',
    }
    fr = _recognizer(resp)
    fr._path = Path(__import__("tempfile").mkdtemp()) / "faces.json"
    fr.register("ana", b"reg")
    out = fr.recognize(b"probe", threshold=0.9)
    assert out["name"] is None
    assert out["present"] is True
