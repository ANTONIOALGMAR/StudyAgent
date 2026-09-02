from app.agent.memory import Memory
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


def test_permission_audit_includes_actor(tmp_path, monkeypatch):
    from app.security import permissions as permissions_module

    caminho = tmp_path / "perm-audit.json"
    monkeypatch.setattr(permissions_module, "AUDIT_LOG_PATH", caminho)
    pm = PermissionManager(path=tmp_path / "p.json")
    pm.set("camera", True, reason="usuario confirmou", actor="alice")
    entries = pm.audit_log(limit=20)
    assert any(entry.get("actor") == "alice" and entry.get("permission") == "camera" for entry in entries)
    assert any(entry.get("actor") == "alice" and entry.get("permission") == "screen_capture" for entry in entries)


def test_environment_memory_is_scoped_by_user(tmp_path):
    db_path = tmp_path / "memory.db"
    memory = Memory(db_path=str(db_path))

    memory.remember_object_location("celular", "mesa da direita", user_id="alice", user_name="Alice")
    memory.remember_object_location("celular", "prateleira esquerda", user_id="bob", user_name="Bob")

    alice = memory.find_object_location("celular", user_id="alice", user_name="Alice")
    bob = memory.find_object_location("celular", user_id="bob", user_name="Bob")

    assert alice["location"] == "mesa da direita"
    assert bob["location"] == "prateleira esquerda"
    assert alice["user_id"] == "alice"
    assert bob["user_id"] == "bob"


def test_environment_memory_can_be_cleared_by_user(tmp_path):
    db_path = tmp_path / "memory.db"
    memory = Memory(db_path=str(db_path))

    memory.remember_object_location("celular", "mesa da direita", user_id="alice", user_name="Alice")
    memory.remember_object_location("celular", "prateleira esquerda", user_id="bob", user_name="Bob")

    deleted = memory.clear_user_memory(user_id="alice")

    assert deleted == 1
    assert memory.find_object_location("celular", user_id="alice", user_name="Alice") is None
    assert memory.find_object_location("celular", user_id="bob", user_name="Bob") is not None
