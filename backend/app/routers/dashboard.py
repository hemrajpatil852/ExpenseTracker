from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Transaction, User
from ..schemas import Filters, SummaryIn
from ..security import current_user
from .transactions import apply_filters

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def bucket(d, group_by):
    if group_by == "day":
        return d.isoformat()
    if group_by == "week":
        return (d - timedelta(days=d.weekday())).isoformat()  # Monday of that week
    return d.strftime("%Y-%m")


@router.post("/summary")
def summary(body: SummaryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    f = Filters(start_date=body.start_date, end_date=body.end_date)

    # totals + per-category in SQL: cost is independent of row count
    cat_rows = (apply_filters(db.query(Category.id, Category.name, Transaction.txn_type,
                                       func.sum(Transaction.amount), func.count(Transaction.id))
                              .select_from(Transaction), user.id, f)
                .join(Category, Category.id == Transaction.category_id)
                .group_by(Category.id, Category.name, Transaction.txn_type).all())
    spent = income = 0.0
    n = 0
    by_cat = defaultdict(lambda: {"spent": 0.0, "income": 0.0, "count": 0})
    for cid, name, typ, total, cnt in cat_rows:
        total = float(total or 0)
        e = by_cat[(cid, name)]
        e["count"] += cnt
        n += cnt
        if typ == "debit":
            e["spent"] += total
            spent += total
        else:
            e["income"] += total
            income += total
    categories = sorted(
        [{"category_id": k[0], "category": k[1], "spent": round(v["spent"], 2), "income": round(v["income"], 2),
          "count": v["count"], "percent": round(v["spent"] / spent * 100, 1) if spent else 0}
         for k, v in by_cat.items() if v["spent"] > 0], key=lambda x: -x["spent"])

    # time series: aggregate per day in SQL, bucket in Python (portable across SQLite/Postgres)
    day_rows = (apply_filters(db.query(Transaction.txn_date, Transaction.txn_type, func.sum(Transaction.amount)),
                              user.id, f).group_by(Transaction.txn_date, Transaction.txn_type).all())
    series = defaultdict(lambda: {"spent": 0.0, "income": 0.0})
    for d, typ, total in day_rows:
        series[bucket(d, body.group_by)]["spent" if typ == "debit" else "income"] += float(total or 0)
    timeline = [{"period": k, "spent": round(v["spent"], 2), "income": round(v["income"], 2)}
                for k, v in sorted(series.items())]

    lo, hi = db.query(func.min(Transaction.txn_date), func.max(Transaction.txn_date)).filter(Transaction.user_id == user.id).one()
    return {"total_spent": round(spent, 2), "total_income": round(income, 2), "net": round(income - spent, 2),
            "transaction_count": n, "categories": categories, "timeline": timeline,
            "data_range": {"min": lo.isoformat() if lo else None, "max": hi.isoformat() if hi else None}}
