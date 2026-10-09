from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Category, Transaction, User
from ..schemas import CategoryCreateIn, Filters, IdIn, TxnListIn, UpdateCategoryIn
from ..categorizer import Categorizer
from ..security import current_user

router = APIRouter(prefix="/api", tags=["transactions"])


def apply_filters(q, user_id: int, f: Filters):
    q = q.filter(Transaction.user_id == user_id)
    if f.start_date:
        q = q.filter(Transaction.txn_date >= f.start_date)
    if f.end_date:
        q = q.filter(Transaction.txn_date <= f.end_date)
    if f.category_id:
        q = q.filter(Transaction.category_id == f.category_id)
    if f.txn_type:
        q = q.filter(Transaction.txn_type == f.txn_type)
    if f.search:
        s = f.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.filter(Transaction.description.ilike(f"%{s}%", escape="\\"))
    return q


def txn_out(t: Transaction):
    return {"id": t.id, "date": t.txn_date.isoformat(), "description": t.description, "amount": float(t.amount),
            "type": t.txn_type, "balance": float(t.balance) if t.balance is not None else None,
            "category_id": t.category_id, "category": t.category.name}


def _accessible_category(db: Session, user_id: int, cid: int) -> Category:
    c = db.query(Category).filter(Category.id == cid, or_(Category.user_id.is_(None), Category.user_id == user_id)).first()
    if not c:
        raise HTTPException(404, "Category not found.")
    return c


@router.post("/transactions/list")
def list_transactions(body: TxnListIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = apply_filters(db.query(Transaction), user.id, body)
    total = q.count()
    items = (q.options(joinedload(Transaction.category))
             .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
             .offset((body.page - 1) * body.page_size).limit(body.page_size).all())
    return {"items": [txn_out(t) for t in items], "total": total, "page": body.page, "page_size": body.page_size}


@router.post("/transactions/update-category")
def update_category(body: UpdateCategoryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = db.query(Transaction).filter(Transaction.id == body.transaction_id, Transaction.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Transaction not found.")
    _accessible_category(db, user.id, body.category_id)
    t.category_id = body.category_id
    db.commit()
    return txn_out(t)


@router.post("/categories/list")
def list_categories(db: Session = Depends(get_db), user: User = Depends(current_user)):
    cats = (db.query(Category).filter(or_(Category.user_id.is_(None), Category.user_id == user.id))
            .order_by(Category.user_id.is_(None), Category.name).all())
    return [{"id": c.id, "name": c.name, "keywords": [k for k in c.keywords.split(",") if k],
             "is_system": c.user_id is None} for c in cats]


@router.post("/categories/create", status_code=201)
def create_category(body: CategoryCreateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    name = body.name.strip()
    if db.query(Category).filter(Category.name.ilike(name), or_(Category.user_id.is_(None), Category.user_id == user.id)).first():
        raise HTTPException(409, "A category with this name already exists.")
    kws = sorted({k.strip().lower() for k in body.keywords if k.strip()})
    cat = Category(user_id=user.id, name=name, keywords=",".join(kws))
    db.add(cat)
    db.commit()
    moved = 0
    if body.reapply and kws:  # only touch rows still sitting in the fallback buckets
        c = Categorizer(db, user.id)
        fallback = [c.debit_default]
        for t in db.query(Transaction).filter(Transaction.user_id == user.id, Transaction.category_id.in_(fallback)):
            if any(k in t.description.lower() for k in kws):
                t.category_id = cat.id
                moved += 1
        db.commit()
    return {"id": cat.id, "name": cat.name, "keywords": kws, "is_system": False, "reassigned": moved}


@router.post("/categories/delete")
def delete_category(body: IdIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cat = db.query(Category).filter(Category.id == body.id, Category.user_id == user.id).first()
    if not cat:
        raise HTTPException(404, "Custom category not found.")
    fallback = Categorizer(db, user.id).debit_default
    db.query(Transaction).filter(Transaction.category_id == cat.id).update({"category_id": fallback})
    db.delete(cat)
    db.commit()
    return {"ok": True}
