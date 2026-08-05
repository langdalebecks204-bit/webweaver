def test_login_ok(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_me_with_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "admin"


def test_me_without_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_users_crud_and_self_delete_guard(client):
    h = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    headers = {"Authorization": f"Bearer {h.json()['access_token']}"}

    created = client.post("/api/users", headers=headers,
                          json={"username": "u1", "password": "pw123456", "role": "viewer"})
    assert created.status_code == 200
    uid = created.json()["id"]

    listed = client.get("/api/users", headers=headers).json()
    assert {u["username"] for u in listed} >= {"admin", "u1"}

    updated = client.put(f"/api/users/{uid}", headers=headers, json={"role": "admin"})
    assert updated.status_code == 200
    assert updated.json()["role"] == "admin"

    me = client.get("/api/auth/me", headers=headers).json()
    denied = client.delete(f"/api/users/{me['id']}", headers=headers)
    assert denied.status_code == 409

    r = client.delete(f"/api/users/{uid}", headers=headers)
    assert r.status_code == 200
    assert "u1" not in {u["username"] for u in client.get("/api/users", headers=headers).json()}


def test_users_requires_admin(client):
    h = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    headers = {"Authorization": f"Bearer {h.json()['access_token']}"}
    client.post("/api/users", headers=headers,
                json={"username": "vr_viewer", "password": "pw123456", "role": "viewer"})

    vh = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'vr_viewer', 'password': 'pw123456'}).json()['access_token']}"}
    assert client.get("/api/users", headers=vh).status_code == 403
    assert client.post("/api/users", headers=vh,
                       json={"username": "x", "password": "pw123456", "role": "viewer"}).status_code == 403
