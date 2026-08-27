from app.security.permissions import PermissionManager


def test_default_negado_e_permitido(tmp_path):
    caminho = tmp_path / "perms.json"
    pm = PermissionManager(path=caminho)
    # arquivo novo: microfone e câmera habilitados por padrão (para uso em app de estudo)
    assert pm.is_allowed("camera")
    assert pm.is_allowed("microphone")
    assert not pm.is_allowed("command_execution")
    assert pm.is_allowed("internet")
    assert pm.is_allowed("screen_capture")


def test_set_e_persistencia(tmp_path):
    caminho = tmp_path / "perms.json"
    pm = PermissionManager(path=caminho)
    pm.set("internet", True)
    assert pm.is_allowed("internet")
    # nova instância lê do disco
    pm2 = PermissionManager(path=caminho)
    assert pm2.is_allowed("internet")
    pm2.set("internet", False)
    assert not PermissionManager(path=caminho).is_allowed("internet")


def test_all_retorna_mapa(tmp_path):
    pm = PermissionManager(path=tmp_path / "p.json")
    mapa = pm.all()
    assert isinstance(mapa, dict)
    assert "microphone" in mapa or "internet" in mapa
