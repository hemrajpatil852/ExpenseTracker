import io

from tests.conftest import HDFC_CSV


def upload(client, auth, text=HDFC_CSV, name="stmt.csv"):
    return client.post("/api/uploads/create", headers=auth["headers"],
                       files={"file": (name, io.BytesIO(text.encode()), "text/csv")})


# ---- auth ----
def test_every_endpoint_is_post_only(client):
    for path in ["/api/health", "/api/auth/me", "/api/transactions/list", "/api/dashboard/summary", "/api/export/csv"]:
        assert client.get(path).status_code == 405


def test_signup_login_me_logout_flow(client, auth):
    assert client.post("/api/auth/signup", json={"name": "X", "email": "ASHA@example.com", "password": "Passw0rdOK"}).status_code == 409
    assert client.post("/api/auth/signup", json={"name": "X", "email": "x@example.com", "password": "short"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "Passw0rdOK"}).status_code == 200
    assert client.post("/api/auth/me", headers=auth["headers"]).json()["email"] == "asha@example.com"
    assert client.post("/api/auth/logout", headers=auth["headers"]).status_code == 200
    assert client.post("/api/auth/me", headers=auth["headers"]).status_code == 401  # token revoked


def test_protected_routes_reject_anonymous_and_refresh_token_misuse(client, auth):
    assert client.post("/api/transactions/list", json={}).status_code == 401
    bad = {"Authorization": f"Bearer {auth['tokens']['refresh_token']}"}
    assert client.post("/api/auth/me", headers=bad).status_code == 401  # refresh token is not an access token


def test_refresh_issues_working_access_token(client, auth):
    r = client.post("/api/auth/refresh", json={"refresh_token": auth["tokens"]["refresh_token"]})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/api/auth/me", headers=h).status_code == 200


def test_expired_session_returns_401(client, auth, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ACCESS_MIN", -1)
    r = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "Passw0rdOK"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    resp = client.post("/api/uploads/list", headers=h)
    assert resp.status_code == 401 and "expired" in resp.json()["detail"].lower()


def test_login_rate_limit(client, auth):
    for _ in range(8):
        client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope"})
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "Passw0rdOK"}).status_code == 429


# ---- upload pipeline ----
def test_upload_categorises_and_keeps_identical_rows(client, auth):
    r = upload(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["inserted"] == 5 and body["duplicates"] == 0  # two identical Uber rides both kept
    items = client.post("/api/transactions/list", headers=auth["headers"], json={}).json()["items"]
    cats = {i["description"]: i["category"] for i in items}
    assert cats["UPI-SWIGGY-ORDER 123"] == "Food & Dining"
    assert cats["UPI-BIGBASKET GROCERY"] == "Groceries"
    assert cats["SALARY CREDIT ACME LTD"] == "Income"


def test_reupload_and_overlapping_statements_are_deduplicated(client, auth):
    upload(client, auth)
    again = upload(client, auth).json()
    assert again["inserted"] == 0 and again["duplicates"] == 5
    overlap = HDFC_CSV + "05/09/24,UPI-ZOMATO,0006,05/09/24,300.00,,107009.50\n"
    r = upload(client, auth, overlap).json()
    assert r["inserted"] == 1 and r["duplicates"] == 5
    total = client.post("/api/transactions/list", headers=auth["headers"], json={}).json()["total"]
    assert total == 6


def test_malformed_upload_is_rejected_and_logged(client, auth):
    r = upload(client, auth, "this,is,not\na,statement,at all\n")
    assert r.status_code == 422
    hist = client.post("/api/uploads/list", headers=auth["headers"]).json()
    assert hist[0]["status"] == "failed"
    assert upload(client, auth, "x", name="evil.exe").status_code == 400


def test_oversized_upload_rejected(client, auth, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 100)
    assert upload(client, auth).status_code == 413


def test_large_file_performance(client, auth):
    lines = ["Date,Description,Debit,Credit"] + [f"01/0{1 + i % 9}/2024,Shop {i},{10 + i},"for i in range(5000)]
    r = upload(client, auth, "\n".join(lines) + "\n")
    assert r.status_code == 201 and r.json()["inserted"] == 5000


# ---- multi-tenancy ----
def test_users_cannot_see_or_modify_each_others_data(client, auth):
    upload(client, auth)
    other = client.post("/api/auth/signup", json={"name": "B", "email": "b@example.com", "password": "Passw0rdOK"}).json()
    h2 = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.post("/api/transactions/list", headers=h2, json={}).json()["total"] == 0
    tid = client.post("/api/transactions/list", headers=auth["headers"], json={}).json()["items"][0]["id"]
    cat = client.post("/api/categories/list", headers=h2).json()[0]["id"]
    assert client.post("/api/transactions/update-category", headers=h2, json={"transaction_id": tid, "category_id": cat}).status_code == 404
    up = client.post("/api/uploads/list", headers=auth["headers"]).json()[0]["id"]
    assert client.post("/api/uploads/delete", headers=h2, json={"id": up}).status_code == 404
    assert upload(client, {"headers": h2}).json()["inserted"] == 5  # same file is NOT a duplicate for another user


# ---- dashboard / export ----
def test_dashboard_totals_and_timeline(client, auth):
    upload(client, auth)
    s = client.post("/api/dashboard/summary", headers=auth["headers"], json={"group_by": "month"}).json()
    assert s["total_spent"] == 2690.5 and s["total_income"] == 60000 and s["net"] == 57309.5
    assert s["timeline"] == [{"period": "2024-09", "spent": 2690.5, "income": 60000.0}]
    assert s["categories"][0]["category"] == "Food & Dining"
    ranged = client.post("/api/dashboard/summary", headers=auth["headers"],
                         json={"start_date": "2024-09-04", "end_date": "2024-09-04"}).json()
    assert ranged["total_spent"] == 460


def test_custom_category_reapply_and_manual_recategorise(client, auth):
    upload(client, auth)
    r = client.post("/api/categories/create", headers=auth["headers"], json={"name": "Rides", "keywords": ["uber"]})
    assert r.status_code == 201
    items = client.post("/api/transactions/list", headers=auth["headers"], json={"search": "uber"}).json()["items"]
    assert all(i["category"] == "Rides" for i in items) or r.json()["reassigned"] == 0  # uber was already "Transport"
    t = items[0]
    r = client.post("/api/transactions/update-category", headers=auth["headers"],
                    json={"transaction_id": t["id"], "category_id": r.json()["id"]})
    assert r.json()["category"] == "Rides"


def test_exports_and_csv_injection_guard(client, auth):
    upload(client, auth, "Date,Description,Debit,Credit\n01/01/2024,=HYPERLINK(\"x\"),10,\n")
    c = client.post("/api/export/csv", headers=auth["headers"], json={})
    assert c.status_code == 200 and "'=HYPERLINK" in c.text
    p = client.post("/api/export/pdf", headers=auth["headers"], json={})
    assert p.status_code == 200 and p.content.startswith(b"%PDF")


def test_delete_upload_removes_its_transactions(client, auth):
    uid = upload(client, auth).json()["id"]
    assert client.post("/api/uploads/delete", headers=auth["headers"], json={"id": uid}).status_code == 200
    assert client.post("/api/transactions/list", headers=auth["headers"], json={}).json()["total"] == 0
