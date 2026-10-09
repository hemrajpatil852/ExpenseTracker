import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: User, kind: str) -> str:
    ttl = timedelta(minutes=config.ACCESS_MIN) if kind == "access" else timedelta(days=config.REFRESH_DAYS)
    payload = {"sub": str(user.id), "ver": user.token_version, "typ": kind,
               "exp": datetime.now(timezone.utc) + ttl}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def decode_token(token: str, kind: str, db: Session) -> User:
    try:
        data = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token.")
    user = db.get(User, int(data.get("sub", 0)))
    if data.get("typ") != kind or not user or user.token_version != data.get("ver"):
        raise HTTPException(401, "Invalid or revoked token.")
    return user


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Not authenticated.")
    return decode_token(creds.credentials, "access", db)


# --- tiny in-memory brute-force limiter (use Redis when running >1 instance) ---
_attempts: dict[str, deque] = defaultdict(deque)
WINDOW, LIMIT = 15 * 60, 8


def check_rate_limit(key: str):
    now, q = time.time(), _attempts[key]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")


def record_failure(key: str):
    _attempts[key].append(time.time())


def clear_failures(key: str):
    _attempts.pop(key, None)
