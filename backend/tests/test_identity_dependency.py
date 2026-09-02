from fastapi.testclient import TestClient
from app.main import app


def test_permissions_endpoint_records_actor_in_audit(tmp_db):
    client = TestClient(app)
    # perform a permissions change with X-User-Id header
    resp = client.put("/api/permissions/camera", json={"value": True, "reason": "aceitar camera"}, headers={"X-User-Id": "alice"})
    assert resp.status_code == 200
    assert resp.json().get("camera") is True

    # fetch audit log and ensure actor recorded
    audit = client.get("/api/permissions/audit")
    assert audit.status_code == 200
    entries = audit.json()
    assert any(e.get("actor") == "alice" and e.get("permission") == "camera" for e in entries), f"audit entries: {entries}"
