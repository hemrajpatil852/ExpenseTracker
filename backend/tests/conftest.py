import os
import tempfile

# Must be set before the app is imported so tests never touch a real database.
_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-123456"

import pytest
from fastapi.testclient import TestClient

from app import security
from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    security._attempts.clear()
    with TestClient(app) as c:  # entering the context runs lifespan: create tables + seed categories
        yield c


@pytest.fixture()
def auth(client):
    r = client.post("/api/auth/signup", json={"name": "Asha", "email": "asha@example.com", "password": "Passw0rdOK"})
    assert r.status_code == 201
    data = r.json()
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}, "tokens": data}


HDFC_CSV = """Account Statement,,,,,,
Customer: ASHA,,,,,,
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/09/24,UPI-SWIGGY-ORDER 123,0001,01/09/24,"1,250.50",,48749.50
02/09/24,UPI-BIGBASKET GROCERY,0002,02/09/24,980.00,,47769.50
03/09/24,SALARY CREDIT ACME LTD,0003,03/09/24,,"60,000.00",107769.50
04/09/24,UPI-UBER INDIA,0004,04/09/24,230.00,,107539.50
04/09/24,UPI-UBER INDIA,0005,04/09/24,230.00,,107309.50
"""
