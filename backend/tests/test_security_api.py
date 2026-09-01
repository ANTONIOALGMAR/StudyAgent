"""Testes de segurança da API: PIN local, rate limiting, CORS e routers via TestClient.

Usa FastAPI TestClient (httpx) contra o app real em `app.main` — evidência de que
os endpoints e as proteções funcionam de ponta a ponta (sem mocks de router).

Cobertura:
- PIN local (`X-StudyAgent-Pin`) exigido para ativar permissões perigosas;
- sem PIN / PIN errado → 401; PIN correto → 200;
- rate limiting (slowapi) em ações de automação → 429 após o limite;
- CORS com origem permitida;
- smoke: /api/health.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.permissions import PermissionManager

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter():
    app.state.limiter.reset()
    yield
    app.state.limiter.reset()


@pytest.fixture
def pin_env(monkeypatch):
    monkeypatch.setenv("STUDYAGENT_PIN", "senha-secreta-123")


@pytest.fixture
def tmp_permissions(monkeypatch, tmp_path):
    """Isola permissões e auditoria em arquivos temporários para os testes de PUT."""
    import app.security.permissions as perm_mod

    perms_file = tmp_path / "permissions.json"
    audit_file = tmp_path / "permission_audit.json"
    monkeypatch.setattr(perm_mod, "AUDIT_LOG_PATH", audit_file)

    class TmpPermissionManager(PermissionManager):
        def __init__(self, path=perms_file):
            super().__init__(path=path)

    monkeypatch.setattr(perm_mod, "PermissionManager", TmpPermissionManager)
    return perms_file, audit_file


# ── PIN local ─────────────────────────────────────────────────────────────────


def test_permissao_perigosa_exige_pin(pin_env):
    resp = client.put("/api/permissions/mouse_control", json={"value": True})
    assert resp.status_code == 401
    assert "PIN" in resp.json()["detail"]


def test_permissao_perigosa_pin_errado(pin_env):
    resp = client.put(
        "/api/permissions/keyboard_control",
        json={"value": True},
        headers={"X-StudyAgent-Pin": "errado"},
    )
    assert resp.status_code == 401


def test_permissao_perigosa_pin_correto(tmp_permissions, pin_env):
    resp = client.put(
        "/api/permissions/command_execution",
        json={"value": True},
        headers={"X-StudyAgent-Pin": "senha-secreta-123"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"command_execution": True}
    import app.security.permissions as perm_mod

    assert perm_mod.PermissionManager().is_allowed("command_execution")


def test_permissao_perigosa_sem_pin_configurado(monkeypatch):
    monkeypatch.delenv("STUDYAGENT_PIN", raising=False)
    resp = client.put("/api/permissions/mouse_control", json={"value": True})
    assert resp.status_code == 401


def test_permissao_nao_perigosa_nao_exige_pin(tmp_permissions, pin_env):
    resp = client.put("/api/permissions/internet", json={"value": False})
    assert resp.status_code == 200
    assert resp.json() == {"internet": False}


def test_grupo_automacao_exige_pin(pin_env):
    resp = client.put("/api/permissions/group/automation", json={"value": True})
    assert resp.status_code == 401


def test_grupo_automacao_pin_correto(tmp_permissions, pin_env):
    resp = client.put(
        "/api/permissions/group/automation",
        json={"value": True},
        headers={"X-StudyAgent-Pin": "senha-secreta-123"},
    )
    assert resp.status_code == 200


# ── Rate limiting ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "endpoint",
    ["/api/actions/nonexistent-id/approve", "/api/actions/nonexistent-id/reject"],
)
def test_rate_limit_actions_20_minute(endpoint):
    # Endpoint retorna 404 (proposta inexistente) — ainda conta no rate limit.
    for _ in range(20):
        assert client.post(endpoint).status_code == 404
    resp = client.post(endpoint)
    assert resp.status_code == 429


# ── CORS ──────────────────────────────────────────────────────────────────────


def test_cors_origem_permitida():
    resp = client.get(
        "/api/health", headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_origem_negada():
    resp = client.get(
        "/api/health", headers={"Origin": "https://evil.example.com"}
    )
    assert "access-control-allow-origin" not in resp.headers


# ── Smoke de routers ──────────────────────────────────────────────────────────


def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
