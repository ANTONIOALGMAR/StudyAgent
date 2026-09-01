from app.security.permissions import PermissionManager


def test_default_negado_e_permitido(tmp_path):
    caminho = tmp_path / "perms.json"
    pm = PermissionManager(path=caminho)
    # permissões sensíveis só são liberadas após identificação do usuário
    assert not pm.is_allowed("camera")
    assert pm.is_allowed("microphone")
    assert not pm.is_allowed("command_execution")
    assert pm.is_allowed("internet")
    assert not pm.is_allowed("screen_capture")


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


def test_permissoes_de_vision_sao_liberadas_apos_identificacao(tmp_path):
    caminho = tmp_path / "perms.json"
    pm = PermissionManager(path=caminho)
    pm.set("camera", False)
    pm.set("screen_capture", False)
    assert not pm.is_allowed("camera")
    assert not pm.is_allowed("screen_capture")

    pm.set("camera", True)
    pm.set("screen_capture", True)
    assert pm.is_allowed("camera")
    assert pm.is_allowed("screen_capture")
    assert PermissionManager(path=caminho).is_allowed("camera")
    assert PermissionManager(path=caminho).is_allowed("screen_capture")


def test_all_retorna_mapa(tmp_path):
    pm = PermissionManager(path=tmp_path / "p.json")
    mapa = pm.all()
    assert isinstance(mapa, dict)
    assert "microphone" in mapa or "internet" in mapa
