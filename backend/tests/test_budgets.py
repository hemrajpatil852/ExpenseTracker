from tests.conftest import HDFC_CSV
from tests.test_api import upload


def cat_id(client, auth, name):
    cats = client.post("/api/categories/list", headers=auth["headers"]).json()
    return next(c["id"] for c in cats if c["name"] == name)


def test_over_budget_flagged_and_ok_when_within_limit(client, auth):
    upload(client, auth)  # Food & Dining spend in Sept 2024 is 1250.50
    food = cat_id(client, auth, "Food & Dining")
    h = auth["headers"]
    assert client.post("/api/budgets/set", headers=h, json={"category_id": food, "monthly_limit": 1000}).status_code == 200
    item = client.post("/api/budgets/status", headers=h, json={"month": "2024-09"}).json()["items"][0]
    assert item["state"] == "over" and item["spent"] == 1250.5 and "Over budget" in item["message"]

    client.post("/api/budgets/set", headers=h, json={"category_id": food, "monthly_limit": 5000})  # update, not duplicate
    res = client.post("/api/budgets/status", headers=h, json={"month": "2024-09"}).json()
    assert len(res["items"]) == 1 and res["items"][0]["state"] == "ok" and res["over_count"] == 0


def test_budget_validation_and_isolation(client, auth):
    h = auth["headers"]
    food = cat_id(client, auth, "Food & Dining")
    assert client.post("/api/budgets/set", headers=h, json={"category_id": food, "monthly_limit": -5}).status_code == 422
    assert client.post("/api/budgets/set", headers=h, json={"category_id": 99999, "monthly_limit": 100}).status_code == 404
    assert client.post("/api/budgets/status", headers=h, json={"month": "2024-13"}).status_code == 422
    client.post("/api/budgets/set", headers=h, json={"category_id": food, "monthly_limit": 100})
    other = client.post("/api/auth/signup", json={"name": "B", "email": "b@example.com", "password": "Passw0rdOK"}).json()
    h2 = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.post("/api/budgets/status", headers=h2, json={}).json()["items"] == []
    assert client.post("/api/budgets/delete", headers=h2, json={"category_id": food}).status_code == 404