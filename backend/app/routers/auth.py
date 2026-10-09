from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginIn, RefreshIn, SignupIn
from ..security import (check_rate_limit, clear_failures, current_user, decode_token, hash_password, make_token,
                        record_failure, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _tokens(u: User):
    return {"access_token": make_token(u, "access"), "refresh_token": make_token(u, "refresh"),
            "user": {"id": u.id, "name": u.name, "email": u.email}}


@router.post("/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")
    u = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.")
    return _tokens(u)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '?'}|{body.email.lower()}"
    check_rate_limit(key)
    u = db.query(User).filter(User.email == body.email.lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        record_failure(key)
        raise HTTPException(401, "Incorrect email or password.")
    clear_failures(key)
    return _tokens(u)


@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    return _tokens(decode_token(body.refresh_token, "refresh", db))


@router.post("/logout")
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.token_version += 1  # invalidates every outstanding access/refresh token
    db.commit()
    return {"ok": True}


@router.post("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}
