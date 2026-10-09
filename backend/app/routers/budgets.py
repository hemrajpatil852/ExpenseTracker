import calendar
import csv
import io

from datetime import date
from decimal import Decimal
from typing import Optional


from fastapi import File, UploadFile

from ..csv_parser import parse_amount
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Budget, Category, Transaction, User
from ..security import current_user

router = APIRouter(prefix="/api/budgets", tags=["budgets"])
inr = lambda v: f"₹{v:,.0f}"


class BudgetSetIn(BaseModel):
    category_id: int
    monthly_limit: Decimal = Field(gt=0, le=Decimal("999999999"))


class BudgetDeleteIn(BaseModel):
    category_id: int


class BudgetStatusIn(BaseModel):
    month: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")  # "2024-09"


@router.post("/set")
def set_budget(body: BudgetSetIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cat = db.query(Category).filter(Category.id == body.category_id,
                                    or_(Category.user_id.is_(None), Category.user_id == user.id)).first()
    if not cat:
        raise HTTPException(404, "Category not found.")
    b = db.query(Budget).filter(Budget.user_id == user.id, Budget.category_id == cat.id).first()
    if b:
        b.monthly_limit = body.monthly_limit
    else:
        db.add(Budget(user_id=user.id, category_id=cat.id, monthly_limit=body.monthly_limit))
    db.commit()
    return {"ok": True}


@router.post("/delete")
def delete_budget(body: BudgetDeleteIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    n = db.query(Budget).filter(Budget.user_id == user.id, Budget.category_id == body.category_id).delete()
    db.commit()
    if not n:
        raise HTTPException(404, "Budget not found.")
    return {"ok": True}


@router.post("/status")
def status(body: BudgetStatusIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    y, m = (int(x) for x in body.month.split("-")) if body.month else (today.year, today.month)
    days = calendar.monthrange(y, m)[1]
    current = (y, m) == (today.year, today.month)
    elapsed = today.day if current else days

    rows = (db.query(Transaction.category_id, func.sum(Transaction.amount))
            .filter(Transaction.user_id == user.id, Transaction.txn_type == "debit",
                    Transaction.txn_date >= date(y, m, 1), Transaction.txn_date <= date(y, m, days))
            .group_by(Transaction.category_id).all())
    spent_by_cat = {cid: float(total or 0) for cid, total in rows}

    items = []
    for b in db.query(Budget).options(joinedload(Budget.category)).filter(Budget.user_id == user.id):
        limit, spent = float(b.monthly_limit), spent_by_cat.get(b.category_id, 0.0)
        projected = spent / elapsed * days if current and elapsed else spent
        pct = spent / limit * 100
        if spent > limit:
            state, msg = "over", f"Over budget by {inr(spent - limit)}."
        elif current and elapsed >= 5 and projected > limit:  # needs a few days of data to be meaningful
            state, msg = "at_risk", f"At this pace you'll spend {inr(projected)}, about {inr(projected - limit)} over budget."
        elif pct >= 80:
            state, msg = "at_risk", f"{pct:.0f}% used. Only {inr(limit - spent)} left."
        else:
            state, msg = "ok", f"{inr(limit - spent)} left."
        items.append({"category_id": b.category_id, "category": b.category.name, "limit": limit,
                      "spent": round(spent, 2), "percent": round(pct, 1), "remaining": round(limit - spent, 2),
                      "projected": round(projected, 2), "state": state, "message": msg})
    items.sort(key=lambda x: -x["percent"])
    return {"month": f"{y}-{m:02d}", "items": items,
            "over_count": sum(i["state"] == "over" for i in items),
            "at_risk_count": sum(i["state"] == "at_risk" for i in items)}


@router.post("/import")
async def import_budgets(file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: User = Depends(current_user)):
    raw = await file.read(100_001)
    if len(raw) > 100_000:
        raise HTTPException(413, "Budget file is too large.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise HTTPException(422, "The file has no rows. Add a header and at least one category.")
    head = [h.strip().lower() for h in rows[0]]
    try:
        ci = next(i for i, h in enumerate(head) if h in ("category", "category name", "name"))
        li = next(i for i, h in enumerate(head) if h in ("monthly limit", "limit", "budget", "monthly budget", "amount"))
    except StopIteration:
        raise HTTPException(422, "The header must have the columns: Category, Monthly Limit.")

    cats = {c.name.lower(): c.id for c in db.query(Category).filter(
        or_(Category.user_id.is_(None), Category.user_id == user.id))}
    existing = {b.category_id: b for b in db.query(Budget).filter(Budget.user_id == user.id)}
    saved, errors = 0, []
    for n, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        name = r[ci].strip() if ci < len(r) else ""
        cid = cats.get(name.lower())
        if cid is None:
            errors.append({"row": n, "reason": f"Unknown category '{name[:40]}'"})
            continue
        try:
            val, _ = parse_amount(r[li] if li < len(r) else "")
        except ValueError:
            errors.append({"row": n, "reason": f"Invalid limit for {name}"})
            continue
        if val is None:  # blank limit: user left this category out on purpose
            continue
        if val <= 0 or val > 999999999:
            errors.append({"row": n, "reason": f"Limit for {name} must be above 0"})
            continue
        if cid in existing:
            existing[cid].monthly_limit = val
        else:
            existing[cid] = Budget(user_id=user.id, category_id=cid, monthly_limit=val)
            db.add(existing[cid])
        saved += 1
    db.commit()
    return {"saved": saved, "errors": errors[:50]}